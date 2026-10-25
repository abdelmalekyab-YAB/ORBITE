from django.db import transaction
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.finance.models import ProjectFinance
from apps.tickets.scope import visible_tickets
from orbit.permissions import IsDigitalia, IsOrbitAdmin, IsPmOrAdmin

from .health import project_health
from .models import Milestone, Project, ProjectAccess, WorkflowStatus
from .scope import visible_projects
from .serializers import (
    MilestoneSerializer,
    ProjectCreateSerializer,
    ProjectSerializer,
    ProjectUpdateSerializer,
    WorkflowStatusSerializer,
)
from .workflow_config import apply_workflow, reset_workflow


def client_steps(statuses) -> list[str]:
    """Piste client : client_label distincts des statuts non clôturés, dans l'ordre, + « Livrée » (03-workflow)."""
    steps: list[str] = []
    for s in statuses:
        if not s.is_closed and s.client_label not in steps:
            steps.append(s.client_label)
    ok = next((s.client_label for s in statuses if s.is_terminal_ok), "Livrée")
    return [*steps, ok]


def project_payload(project, user) -> dict:
    tickets = visible_tickets(user).filter(project=project)
    open_qs = tickets.filter(status__is_closed=False)
    return {**ProjectSerializer(project).data, **project_health(tickets),
            "counts": {"open": open_qs.count(), "client": open_qs.filter(status__ball="client").count(),
                       "digitalia": open_qs.filter(status__ball="digitalia").count(),
                       "delivered": tickets.filter(status__is_terminal_ok=True).count(),
                       "late": sum(1 for t in open_qs.filter(due_on__isnull=False) if t.is_late)}}


class ProjectListView(APIView):
    def get(self, request):
        include_archived = request.user.is_digitalia and request.query_params.get("include_archived") == "1"
        projects = visible_projects(request.user, include_archived)
        return Response([project_payload(p, request.user) for p in projects])

    @transaction.atomic
    def post(self, request):
        """Admin : crée le projet + ses finances, et ouvre l'accès aux utilisateurs du client."""
        if not IsOrbitAdmin().has_permission(request, self):
            raise PermissionDenied("Réservé aux administrateurs Digitalia.")
        s = ProjectCreateSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        d = s.validated_data
        project = Project.objects.create(key=d["key"], name=d["name"], description=d.get("description", ""),
                                         client=d["client"], lead=d.get("lead"))
        ProjectFinance.objects.create(project=project, dev_price=d.get("dev_price") or 0,
                                      licence_amount=d.get("licence_amount") or 0,
                                      licence_start=d.get("licence_start"))
        for user in d["client"].users.filter(is_active=True):
            ProjectAccess.objects.get_or_create(user=user, project=project)
        return Response(project_payload(project, request.user), status=status.HTTP_201_CREATED)


class ProjectDetailView(APIView):
    def get(self, request, key):
        project = get_object_or_404(visible_projects(request.user, request.user.is_digitalia), key=key.upper())
        data = project_payload(project, request.user)
        data["milestones"] = MilestoneSerializer(project.milestones.all(), many=True).data
        return Response(data)

    def patch(self, request, key):
        """pm / admin : nom, description, responsable."""
        if not IsPmOrAdmin().has_permission(request, self):
            raise PermissionDenied("Réservé aux chefs de projet et administrateurs.")
        project = get_object_or_404(Project, key=key.upper())
        s = ProjectUpdateSerializer(project, data=request.data, partial=True)
        s.is_valid(raise_exception=True)
        s.save()
        return Response(project_payload(project, request.user))


class ProjectArchiveView(APIView):
    """POST /projects/{key}/archive | /unarchive — admin."""

    permission_classes = [IsOrbitAdmin]

    def post(self, request, key, action):
        project = get_object_or_404(Project, key=key.upper())
        project.is_archived = action == "archive"
        project.save(update_fields=["is_archived", "updated_at"])
        return Response(project_payload(project, request.user))


class MilestoneListView(APIView):
    """GET : tous (scope) ; POST : Digitalia."""

    def get(self, request, key):
        project = get_object_or_404(visible_projects(request.user), key=key.upper())
        return Response(MilestoneSerializer(project.milestones.all(), many=True).data)

    def post(self, request, key):
        if not request.user.is_digitalia:
            raise PermissionDenied("Réservé à l'équipe Digitalia.")
        project = get_object_or_404(visible_projects(request.user), key=key.upper())
        s = MilestoneSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        order = s.validated_data.get("order") or project.milestones.count() + 1
        s.save(project=project, order=order)
        return Response(s.data, status=status.HTTP_201_CREATED)


class MilestoneDetailView(APIView):
    """PATCH / DELETE /projects/{key}/milestones/{id} — Digitalia. Les tickets de la version sont dé-planifiés."""

    permission_classes = [IsDigitalia]

    def _get(self, key, pk):
        return get_object_or_404(Milestone, project__key=key.upper(), pk=pk)

    def patch(self, request, key, pk):
        s = MilestoneSerializer(self._get(key, pk), data=request.data, partial=True)
        s.is_valid(raise_exception=True)
        s.save()
        return Response(s.data)

    def delete(self, request, key, pk):
        self._get(key, pk).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


def workflow_payload(project):
    statuses = list(WorkflowStatus.for_project(project).prefetch_related("next"))
    return {"statuses": WorkflowStatusSerializer(statuses, many=True).data, "steps": client_steps(statuses),
            "customized": bool(project and WorkflowStatus.objects.filter(project=project).exists())}


class WorkflowView(APIView):
    """GET : tous ; PUT : pm/admin (remplace la config ; 409 si suppression d'un statut utilisé ou système)."""

    def _project(self, request):
        if key := request.query_params.get("project"):
            return get_object_or_404(visible_projects(request.user), key=key.upper())
        return None

    def get(self, request):
        return Response(workflow_payload(self._project(request)))

    def put(self, request):
        if not IsPmOrAdmin().has_permission(request, self):
            raise PermissionDenied("Réservé aux chefs de projet et administrateurs.")
        project = self._project(request)
        spec = request.data.get("statuses") if isinstance(request.data, dict) else request.data
        apply_workflow(project, spec if isinstance(spec, list) else [])
        return Response(workflow_payload(project))


class WorkflowResetView(APIView):
    permission_classes = [IsPmOrAdmin]

    def post(self, request):
        project = None
        if key := request.query_params.get("project"):
            project = get_object_or_404(Project, key=key.upper())
        reset_workflow(project)
        return Response(workflow_payload(project))
