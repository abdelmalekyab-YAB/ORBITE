"""Cockpit et Équipe (espace Digitalia) — docs/05-api.md."""
from django.utils import timezone
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.models import User
from apps.accounts.serializers import UserMiniSerializer
from apps.projects.scope import visible_projects
from apps.projects.views import project_payload
from orbit.permissions import IsDigitalia

from .models import TicketEvent
from .scope import visible_tickets
from .serializers import TicketEventSerializer, TicketSerializer

# « À traiter maintenant » : clé, libellé, filtre sur les tickets ouverts
BUCKETS = [("late", "En retard", None), ("nouveau", "À qualifier", "nouveau"), ("attente", "Attente client", "attente"),
           ("devis", "Devis en attente", "devis"), ("testint", "À valider en interne", "testint"),
           ("test", "En test client", "test")]


def digitalia_members():
    return User.objects.filter(organization__kind="digitalia", is_active=True).order_by("first_name")


class CockpitView(APIView):
    permission_classes = [IsDigitalia]

    def get(self, request):
        ctx = {"request": request}
        open_qs = visible_tickets(request.user).filter(status__is_closed=False, project__is_archived=False)
        today = timezone.localdate()
        to_handle = []
        for key, label, status_key in BUCKETS:
            qs = open_qs.filter(due_on__lt=today) if key == "late" else open_qs.filter(status__key=status_key)
            to_handle.append({"key": key, "label": label,
                              "tickets": TicketSerializer(qs.order_by("due_on", "number"), many=True,
                                                          context=ctx).data})
        workload = [{"user": UserMiniSerializer(u).data, "open": open_qs.filter(assignee=u).count(),
                     "late": open_qs.filter(assignee=u, due_on__lt=today).count()} for u in digitalia_members()]
        activity = TicketEvent.objects.select_related("actor", "ticket__project").order_by("-at", "-id")[:20]
        return Response({
            "projects": [project_payload(p, request.user) for p in visible_projects(request.user)],
            "to_handle": to_handle,
            "workload": workload,
            "activity": [{**TicketEventSerializer(e).data, "ticket": {"id": e.ticket_id, "ref": e.ticket.ref,
                                                                       "title": e.ticket.title}} for e in activity],
        })


class ActivityView(APIView):
    """« Ce qui a bougé » : derniers événements sur les tickets visibles (règles 1-2), `?project=KEY` optionnel."""

    def get(self, request):
        tickets = visible_tickets(request.user)
        if key := request.query_params.get("project"):
            tickets = tickets.filter(project__key=key.upper())
        events = (TicketEvent.objects.filter(ticket__in=tickets).select_related("actor", "ticket__project")
                  .order_by("-at", "-id")[:15])
        return Response([{**TicketEventSerializer(e).data, "ticket": {"id": e.ticket_id, "ref": e.ticket.ref,
                                                                       "title": e.ticket.title}} for e in events])


class TeamView(APIView):
    permission_classes = [IsDigitalia]

    def get(self, request):
        open_qs = visible_tickets(request.user).filter(status__is_closed=False)
        today = timezone.localdate()
        members = []
        for u in digitalia_members():
            mine = open_qs.filter(assignee=u).order_by("due_on", "number")
            members.append({"user": {**UserMiniSerializer(u).data, "email": u.email},
                            "open": mine.count(), "late": mine.filter(due_on__lt=today).count(),
                            "tickets": TicketSerializer(mine, many=True, context={"request": request}).data})
        return Response({"members": members, "unassigned": open_qs.filter(assignee__isnull=True).count()})
