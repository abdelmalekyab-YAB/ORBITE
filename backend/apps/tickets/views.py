from typing import Any, cast

from django.db.models import Q
from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import NotFound, PermissionDenied
from rest_framework.pagination import CursorPagination
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.models import User
from apps.notifications import service as notifications
from apps.projects.models import WorkflowStatus
from apps.projects.scope import visible_projects
from orbit.permissions import IsDigitalia, IsPmOrAdmin

from . import quotes, workflow
from .models import Comment, Quote, Ticket
from .scope import visible_tickets
from .serializers import (
    IMPACT_TO_PRIORITY,
    QuoteInputSerializer,
    QuoteSerializer,
    TicketCreateSerializer,
    TicketDetailSerializer,
    TicketEventSerializer,
    TicketSerializer,
    TicketUpdateSerializer,
    TriageSerializer,
)
from .triage import TRIAGE_STATUSES
from .triage import triage as triage_ticket
from .workflow import BusinessError


class TicketPagination(CursorPagination):
    ordering = ("-updated_at", "-id")
    page_size = 200


def _truthy(value) -> bool:
    return str(value).lower() in ("1", "true", "yes")


def filter_tickets(qs, params, user):
    if v := params.get("project"):
        qs = qs.filter(project__key__in=v.upper().split(","))
    if v := params.get("status"):
        qs = qs.filter(status__key__in=v.split(","))
    if v := params.get("ball"):
        qs = qs.filter(status__ball=v, status__is_closed=False)
    if v := params.get("type"):
        qs = qs.filter(type__in=v.split(","))
    if v := params.get("priority"):
        qs = qs.filter(priority__in=v.split(","))
    if v := params.get("origin"):
        qs = qs.filter(origin=v)
    if v := params.get("milestone"):
        qs = qs.filter(milestone__isnull=True) if v == "none" else qs.filter(milestone_id=v)
    if v := params.get("assignee"):
        qs = {"me": qs.filter(assignee=user), "none": qs.filter(assignee__isnull=True)}.get(v) or qs.filter(
            assignee_id=v)
    if v := params.get("parent"):
        qs = qs.filter(parent__isnull=True) if v == "none" else qs.filter(parent_id=v)
    if _truthy(params.get("late")):
        qs = qs.filter(due_on__lt=timezone.localdate(), status__is_closed=False)
    if (v := params.get("closed")) is not None:
        qs = qs.filter(status__is_closed=_truthy(v))
    if v := params.get("q"):
        cond = Q(title__icontains=v) | Q(description__icontains=v)
        if "-" in v:
            key, _, num = v.rpartition("-")
            if num.isdigit():
                cond |= Q(project__key__iexact=key, number=int(num))
        elif v.isdigit():
            cond |= Q(number=int(v))
        qs = qs.filter(cond)
    return qs


class TicketViewSet(viewsets.GenericViewSet):
    parser_classes = (JSONParser, MultiPartParser, FormParser)
    pagination_class = TicketPagination

    def get_queryset(self):
        return visible_tickets(self.request.user)

    def _detail(self, ticket, code=status.HTTP_200_OK):
        ticket = self.get_queryset().prefetch_related("comments__author__organization", "comments__attachments",
                                                      "status__next").get(pk=ticket.pk)
        return Response(TicketDetailSerializer(ticket, context={"request": self.request}).data, status=code)

    # GET /tickets
    def list(self, request):
        qs = filter_tickets(self.get_queryset(), request.query_params, request.user)
        page = self.paginate_queryset(qs)
        return self.get_paginated_response(TicketSerializer(page, many=True, context={"request": request}).data)

    # POST /tickets (multipart) — règles 7 et 8
    def create(self, request):
        s = TicketCreateSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        d = s.validated_data
        user = request.user
        project = visible_projects(user).filter(key=d["project"].upper()).first()
        if project is None:
            raise PermissionDenied("Vous n'avez pas accès à ce projet.")
        files = request.FILES.getlist("attachments")
        if user.is_digitalia:
            is_internal = d["is_internal"] or d["type"] == Ticket.Type.INTERNAL
            if d.get("parent") and d["parent"].project_id != project.id:
                raise BusinessError("La tâche parente doit appartenir au même projet.", "invalid_parent")
            if d.get("milestone") and d["milestone"].project_id != project.id:
                raise BusinessError("Cette version n'appartient pas au projet.", "invalid_milestone")
            ticket = workflow.create_ticket(
                project=project, author=user, status_key=d["initial_status"], attachments=files, type=d["type"],
                title=d["title"], description=d["description"], priority=d.get("priority", "normal"),
                origin=Ticket.Origin.DIGITALIA, is_internal=is_internal, assignee=d.get("assignee"),
                milestone=d.get("milestone"), due_on=d.get("due_on"), parent=d.get("parent"))
        else:
            if d["type"] == Ticket.Type.INTERNAL:
                raise BusinessError("Type de demande non disponible.", "invalid_type")
            priority = IMPACT_TO_PRIORITY.get(d.get("impact", ""), d.get("priority", "normal"))
            if priority not in IMPACT_TO_PRIORITY.values():
                priority = "normal"
            ticket = workflow.create_ticket(
                project=project, author=user, status_key="nouveau", attachments=files, type=d["type"],
                title=d["title"], description=d["description"], priority=priority, origin=Ticket.Origin.CLIENT,
                is_internal=False)
        return self._detail(ticket, status.HTTP_201_CREATED)

    # GET /tickets/{id}
    def retrieve(self, request, pk=None):
        return self._detail(self.get_object())

    # PATCH /tickets/{id} — client : rien ; Digitalia : champs de pilotage
    def partial_update(self, request, pk=None):
        ticket = self.get_object()
        if not request.user.is_digitalia:
            raise PermissionDenied("Vous ne pouvez pas modifier cette demande.")
        s = TicketUpdateSerializer(ticket, data=request.data, partial=True)
        s.is_valid(raise_exception=True)
        workflow.update_fields(ticket, request.user, dict(s.validated_data))
        return self._detail(ticket)

    # POST /tickets/{id}/transition — règles 9 et 10
    @action(detail=True, methods=["post"])
    def transition(self, request, pk=None):
        ticket = self.get_object()
        to = request.data.get("to")
        if not to:
            raise BusinessError("Statut cible manquant.", "missing_to")
        workflow.transition(ticket, to, request.user, comment=request.data.get("comment"),
                            attachments=request.FILES.getlist("attachments"))
        return self._detail(ticket)

    # POST /tickets/{id}/comments — règle 11
    @action(detail=True, methods=["post"])
    def comments(self, request, pk=None):
        ticket = self.get_object()
        body = (request.data.get("body") or "").strip()
        files = request.FILES.getlist("attachments")
        if not body and not files:
            raise BusinessError("Le message est vide.", "empty_comment")
        workflow.add_comment(ticket, request.user, body, attachments=files)
        notifications.on_client_comment(ticket, request.user)
        if not request.user.is_digitalia and ticket.status.key == "attente":
            workflow.transition(ticket, "cours", request.user)
        return self._detail(ticket, status.HTTP_201_CREATED)

    # GET /tickets/{id}/events
    @action(detail=True, methods=["get"])
    def events(self, request, pk=None):
        ticket = self.get_object()
        return Response(TicketEventSerializer(ticket.events.select_related("actor"), many=True).data)

    # POST /tickets/{id}/ping — relance, pas de transition
    @action(detail=True, methods=["post"], permission_classes=[IsDigitalia])
    def ping(self, request, pk=None):
        ticket = self.get_object()
        body = (request.data.get("body") or "").strip() or "Petite relance : pouvez-vous nous faire un retour ?"
        workflow.add_comment(ticket, request.user, body, kind=Comment.Kind.PING)
        workflow.log(ticket, request.user, "ping", message="a relancé le client")
        notifications.on_ping(ticket, request.user)
        return self._detail(ticket, status.HTTP_201_CREATED)

    # POST /tickets/{id}/triage — règles 13-14
    @action(detail=True, methods=["post"], permission_classes=[IsPmOrAdmin])
    def triage(self, request, pk=None):
        ticket = self.get_object()
        s = TriageSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        d = s.validated_data
        changes = {f: d[f] for f in TriageSerializer.FIELDS if f in d}
        milestone = changes.get("milestone")
        if milestone and milestone.project_id != ticket.project_id:
            raise BusinessError("Cette version n'appartient pas au projet.", "invalid_milestone")
        triage_ticket(ticket, request.user, decision=d["decision"], changes=changes, message=d["message"],
                      quote=s.quote_data(), pdf=d.get("quote_pdf"))
        return self._detail(ticket)

    def _quote(self, ticket) -> Quote:
        quote = getattr(ticket, "quote", None) if hasattr(ticket, "quote") else None
        if quote is None or (not cast(User, self.request.user).is_digitalia and quote.status == Quote.Status.DRAFT
                             and quote.sent_at is None):
            raise NotFound("Aucune proposition pour cette demande.")
        return quote

    # GET / PATCH /tickets/{id}/quote — PATCH : pm/admin, repasse en brouillon (règle 18)
    @action(detail=True, methods=["get", "patch"], url_path="quote")
    def quote(self, request, pk=None):
        ticket = self.get_object()
        quote = self._quote(ticket)
        if request.method == "PATCH":
            if not IsPmOrAdmin().has_permission(request, self):
                raise PermissionDenied("Réservé aux chefs de projet et administrateurs.")
            s = QuoteInputSerializer(data=request.data, partial=True)
            s.is_valid(raise_exception=True)
            quote = quotes.update_quote(quote, request.user, pdf=request.FILES.get("pdf"), **s.validated_data)
        return Response(QuoteSerializer(quote, context={"request": request}).data)

    # POST /tickets/{id}/quote/send — renvoi après modification
    @action(detail=True, methods=["post"], url_path="quote/send", permission_classes=[IsPmOrAdmin])
    def quote_send(self, request, pk=None):
        ticket = self.get_object()
        self._quote(ticket)
        quotes.send_quote(ticket, request.user)
        return self._detail(ticket)

    # POST /tickets/{id}/quote/accept — client (règle 16)
    @action(detail=True, methods=["post"], url_path="quote/accept")
    def quote_accept(self, request, pk=None):
        ticket = self.get_object()
        quotes.accept_quote(ticket, request.user)
        return self._detail(ticket)

    # POST /tickets/{id}/quote/refuse — client, motif obligatoire (règle 17)
    @action(detail=True, methods=["post"], url_path="quote/refuse")
    def quote_refuse(self, request, pk=None):
        ticket = self.get_object()
        quotes.refuse_quote(ticket, request.user, reason=request.data.get("reason"),
                            attachments=request.FILES.getlist("attachments"))
        return self._detail(ticket)

    # GET /tickets/board?project=KEY — colonnes issues du workflow
    @action(detail=False, methods=["get"], permission_classes=[IsDigitalia])
    def board(self, request):
        project = None
        if key := request.query_params.get("project"):
            project = visible_projects(request.user).filter(key=key.upper()).first()
        columns: list[dict[str, Any]] = []
        client_col: dict[str, Any] | None = None
        for st in WorkflowStatus.for_project(project):
            if st.is_closed and not st.is_terminal_ok:
                continue
            if st.ball == WorkflowStatus.Ball.CLIENT:
                if client_col is None:
                    client_col = {"key": "client", "label": "Chez le client", "ball": "client", "statuses": []}
                    columns.append(client_col)
                client_col["statuses"].append(st.key)
            else:
                columns.append({"key": st.key, "label": st.label, "ball": st.ball, "statuses": [st.key]})
        qs = filter_tickets(self.get_queryset(), request.query_params, request.user).exclude(
            status__is_closed=True, status__is_terminal_ok=False)
        cards = TicketSerializer(qs.order_by("due_on", "project__key", "number"), many=True,
                                 context={"request": request}).data
        for col in columns:
            col["cards"] = [c for c in cards if c["status"] in col["statuses"]]
        return Response({"columns": columns})


class TriageListView(APIView):
    """GET /triage — file des demandes nouvelles et en analyse, tous projets, plus anciennes d'abord."""

    permission_classes = [IsPmOrAdmin]

    def get(self, request):
        qs = visible_tickets(request.user).filter(status__key__in=TRIAGE_STATUSES, project__is_archived=False)
        return Response(TicketSerializer(qs.order_by("created_at", "id"), many=True, context={"request": request}).data)
