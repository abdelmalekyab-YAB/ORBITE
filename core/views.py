from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.translation import gettext as _

from tickets.models import Ticket
from tickets.services import progress, ticket_stats

from .forms import MilestoneForm
from .models import Company, Milestone
from .permissions import digitalia_required, get_project_for


@login_required
def home(request):
    user = request.user
    if user.is_digitalia:
        return redirect("dashboard")
    projects = list(user.visible_projects().filter(is_active=True))
    if len(projects) == 1:
        return redirect(projects[0])
    return render(request, "core/project_picker.html", {"projects": projects})


def _milestones_with_progress(project, user):
    milestones = project.milestones.all()
    if not user.is_digitalia:
        milestones = milestones.filter(is_client_visible=True)
    tickets = Ticket.objects.visible_to(user)
    result = []
    for milestone in milestones:
        stats = ticket_stats(tickets.filter(milestone=milestone))
        result.append({"milestone": milestone, "stats": stats, "progress": progress(stats)})
    return result


@login_required
def project_detail(request, key):
    project = get_project_for(request.user, key)
    tickets = Ticket.objects.visible_to(request.user).filter(project=project).select_related("project", "assignee")
    stats = ticket_stats(tickets)
    today = timezone.localdate()
    context = {
        "project": project,
        "stats": stats,
        "progress": progress(stats),
        "milestones": _milestones_with_progress(project, request.user),
        "in_progress": tickets.filter(status__in=[Ticket.Status.IN_PROGRESS, Ticket.Status.IN_TEST])[:10],
        "waiting_client": tickets.filter(status=Ticket.Status.WAITING_CLIENT)[:10],
        "upcoming": tickets.open().filter(due_date__gte=today).order_by("due_date")[:10],
        "recently_done": tickets.filter(status=Ticket.Status.DONE).order_by("-closed_at")[:10],
    }
    return render(request, "core/project_detail.html", context)


@login_required
def roadmap(request, key):
    project = get_project_for(request.user, key)
    milestones = _milestones_with_progress(project, request.user)
    visible = Ticket.objects.visible_to(request.user).filter(project=project, parent__isnull=True)
    for item in milestones:
        item["tickets"] = visible.filter(milestone=item["milestone"]).order_by("status", "-priority")
    unplanned = visible.open().filter(milestone__isnull=True)
    return render(request, "core/roadmap.html", {"project": project, "milestones": milestones, "unplanned": unplanned})


@digitalia_required
def milestone_edit(request, key, pk=None):
    project = get_project_for(request.user, key)
    milestone = get_object_or_404(Milestone, pk=pk, project=project) if pk else Milestone(project=project)
    form = MilestoneForm(request.POST or None, instance=milestone)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, _("Roadmap step saved."))
        return redirect("roadmap", key=project.key)
    return render(request, "core/milestone_form.html", {"project": project, "form": form, "milestone": milestone})


@digitalia_required
def dashboard(request):
    projects = []
    base = Ticket.objects.all()
    for project in request.user.visible_projects().filter(is_active=True).select_related("company", "lead"):
        stats = ticket_stats(base.filter(project=project))
        projects.append({"project": project, "stats": stats, "progress": progress(stats)})
    today = timezone.localdate()
    context = {
        "projects": projects,
        "totals": ticket_stats(base.filter(project__is_active=True)),
        "late": base.late().select_related("project", "assignee").order_by("due_date")[:15],
        "upcoming": base.open().filter(due_date__gte=today).select_related("project", "assignee").order_by("due_date")[:15],
        "new_client": base.filter(origin=Ticket.Origin.CLIENT, status=Ticket.Status.NEW).select_related("project")[:15],
        "mine": base.open().filter(assignee=request.user).select_related("project")[:15],
    }
    return render(request, "core/dashboard.html", context)


@digitalia_required
def client_list(request):
    open_q = ~Q(projects__tickets__status__in=Ticket.CLOSED_STATUSES)
    companies = Company.objects.filter(is_internal=False).annotate(
        n_projects=Count("projects", distinct=True),
        n_users=Count("users", distinct=True),
        n_open=Count("projects__tickets", filter=open_q, distinct=True),
    ).prefetch_related("projects")
    return render(request, "core/client_list.html", {"companies": companies})


@digitalia_required
def project_list(request):
    projects = request.user.visible_projects().select_related("company", "lead").annotate(
        n_members=Count("members", distinct=True),
        n_open=Count("tickets", filter=~Q(tickets__status__in=Ticket.CLOSED_STATUSES), distinct=True),
    )
    return render(request, "core/project_list.html", {"projects": projects})


@digitalia_required
def team(request):
    open_q = ~Q(assigned_tickets__status__in=Ticket.CLOSED_STATUSES)
    members = get_user_model().objects.filter(Q(role="staff") | Q(is_superuser=True), is_active=True).annotate(
        n_open=Count("assigned_tickets", filter=open_q, distinct=True),
        n_late=Count(
            "assigned_tickets",
            filter=open_q & Q(assigned_tickets__due_date__lt=timezone.localdate()),
            distinct=True,
        ),
    ).order_by("first_name", "username")
    return render(request, "core/team.html", {"members": members})
