"""Kanban boards: a simple read-only board for clients, a drag & drop board for Digitalia."""
import datetime
import json

from django.contrib.auth.decorators import login_required
from django.db.models import Count, Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render
from django.utils import timezone
from django.utils.translation import gettext as _
from django.utils.translation import gettext_lazy
from django.views.decorators.http import require_POST

from core.models import Project
from core.permissions import digitalia_required, get_project_for

from .forms import staff_users
from .models import Ticket
from .services import record_changes, snapshot

S = Ticket.Status

# Digitalia sees one column per working status; rejected/cancelled are dropped on "Done/closed" only via edit.
STAFF_COLUMNS = [
    (S.NEW, [S.NEW]),
    (S.TO_ANALYSE, [S.TO_ANALYSE]),
    (S.TODO, [S.TODO]),
    (S.IN_PROGRESS, [S.IN_PROGRESS]),
    (S.WAITING_CLIENT, [S.WAITING_CLIENT]),
    (S.IN_TEST, [S.IN_TEST]),
    (S.DONE, [S.DONE]),
]

# Clients see five plain-language columns.
CLIENT_COLUMNS = [
    ("received", gettext_lazy("Received"), [S.NEW, S.TO_ANALYSE]),
    ("planned", gettext_lazy("Planned"), [S.TODO]),
    ("in_progress", gettext_lazy("In progress"), [S.IN_PROGRESS]),
    ("your_turn", gettext_lazy("Your turn: answer or test"), [S.WAITING_CLIENT, S.IN_TEST]),
    ("done", gettext_lazy("Done"), [S.DONE]),
]

GROUPS = {
    "": gettext_lazy("None"),
    "project": gettext_lazy("Project"),
    "assignee": gettext_lazy("Assignee"),
    "priority": gettext_lazy("Priority"),
    "type": gettext_lazy("Type"),
}

DONE_DAYS = 30


def _base_queryset(user, project=None):
    qs = Ticket.objects.visible_to(user).exclude(status__in=[S.REJECTED, S.CANCELLED])
    # Only recently closed tickets stay on the board.
    since = timezone.now() - datetime.timedelta(days=DONE_DAYS)
    qs = qs.exclude(status=S.DONE, closed_at__lt=since)
    if project is not None:
        qs = qs.filter(project=project)
    return qs.select_related("project__company", "assignee", "milestone").annotate(
        n_subtasks=Count("subtasks", distinct=True),
        n_comments=Count("comments", filter=Q(comments__is_internal=False), distinct=True),
    )


def _apply_filters(request, qs):
    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(Q(title__icontains=q) | Q(description__icontains=q))
    for name in ("type", "priority"):
        if request.GET.get(name):
            qs = qs.filter(**{name: request.GET[name]})
    assignee = request.GET.get("assignee")
    if assignee == "me":
        qs = qs.filter(assignee=request.user)
    elif assignee == "none":
        qs = qs.filter(assignee__isnull=True)
    elif assignee and assignee.isdigit():
        qs = qs.filter(assignee_id=assignee)
    if request.GET.get("project", "").isdigit():
        qs = qs.filter(project_id=request.GET["project"])
    if request.GET.get("milestone", "").isdigit():
        qs = qs.filter(milestone_id=request.GET["milestone"])
    if request.GET.get("origin"):
        qs = qs.filter(origin=request.GET["origin"])
    if request.GET.get("subtasks") != "1":
        qs = qs.filter(parent__isnull=True)
    return qs


def _lanes(tickets, group):
    """Split tickets into swimlanes: list of (label, tickets)."""
    if not group:
        return [(None, tickets)]
    lanes = {}
    for t in tickets:
        if group == "project":
            key, label = t.project_id, f"{t.project.name} · {t.project.company}"
        elif group == "assignee":
            key, label = t.assignee_id or 0, str(t.assignee) if t.assignee else _("Unassigned")
        elif group == "priority":
            key, label = Ticket.Priority.values.index(t.priority) * -1, t.get_priority_display()
        else:
            key, label = t.type, t.get_type_display()
        lanes.setdefault(key, [label, []])[1].append(t)
    ordered = sorted(lanes.items(), key=lambda kv: (kv[1][0] if group in ("project", "assignee", "type") else kv[0]))
    return [(label, items) for _key, (label, items) in ordered]


def _build(tickets, columns_spec, group):
    from .views import PRIORITY_ORDER

    tickets = list(tickets.order_by(PRIORITY_ORDER.asc(), "due_date", "number"))
    lanes = []
    for label, items in _lanes(tickets, group):
        cols = []
        for key, title, statuses in columns_spec:
            cols.append({"key": key, "title": title, "tickets": [t for t in items if t.status in statuses]})
        lanes.append({"label": label, "columns": cols, "count": len(items)})
    totals = [
        {"key": key, "title": title, "count": sum(1 for t in tickets if t.status in statuses)}
        for key, title, statuses in columns_spec
    ]
    return lanes, totals


def _staff_columns():
    return [(status.value, status.label, statuses) for status, statuses in STAFF_COLUMNS]


def _render(request, project=None):
    user = request.user
    qs = _apply_filters(request, _base_queryset(user, project))
    if user.is_digitalia:
        default_group = "" if project else "project"
        group = request.GET.get("group", default_group)
        group = group if group in GROUPS and not (project and group == "project") else default_group
        lanes, totals = _build(qs, _staff_columns(), group)
    else:
        group = ""
        lanes, totals = _build(qs, CLIENT_COLUMNS, group)
    groups = {k: v for k, v in GROUPS.items() if not (project and k == "project")}
    return render(request, "tickets/board.html", {
        "project": project,
        "lanes": lanes,
        "totals": totals,
        "group": group,
        "groups": groups,
        "types": Ticket.Type.choices if user.is_digitalia else [c for c in Ticket.Type.choices if c[0] in Ticket.CLIENT_TYPES],
        "priorities": Ticket.Priority.choices,
        "origins": Ticket.Origin.choices,
        "assignees": staff_users() if user.is_digitalia else [],
        "projects": user.visible_projects().filter(is_active=True) if project is None else [],
        "milestones": project.milestones.all() if project and user.is_digitalia
        else project.milestones.filter(is_client_visible=True) if project else [],
        "can_drag": user.is_digitalia,
        "done_days": DONE_DAYS,
    })


@login_required
def project_board(request, key):
    return _render(request, get_project_for(request.user, key))


@digitalia_required
def global_board(request):
    return _render(request)


@require_POST
@digitalia_required
def move_ticket(request, pk):
    ticket = get_object_or_404(Ticket, pk=pk)
    try:
        status = json.loads(request.body or "{}").get("status")
    except ValueError:
        status = None
    if status not in Ticket.Status.values:
        return JsonResponse({"error": _("Unknown status.")}, status=400)
    if ticket.status != status:
        before = snapshot(ticket)
        ticket.status = status
        ticket.save()
        record_changes(ticket, before, request.user)
    return JsonResponse({"ok": True, "status": ticket.status, "label": ticket.get_status_display()})
