from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Case, IntegerField, Value, When
from django.http import FileResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.translation import gettext as _

from core.permissions import digitalia_required, get_project_for

from . import notifications
from .forms import ClientTicketForm, CommentForm, StaffTicketForm, TicketFilterForm
from .models import Attachment, Ticket, TicketEvent
from .services import record_changes, record_creation, snapshot

PRIORITY_ORDER = Case(
    *[When(priority=value, then=Value(i)) for i, value in enumerate(reversed(Ticket.Priority.values))],
    output_field=IntegerField(),
)
SORTS = {
    "created": ["-created_at"],
    "updated": ["-updated_at"],
    "due": ["due_date", "-created_at"],
    "priority": [PRIORITY_ORDER.asc(), "-created_at"],
}


def _get_ticket(user, key, number):
    project = get_project_for(user, key)
    qs = Ticket.objects.visible_to(user).select_related("project__company", "author", "assignee", "milestone", "parent")
    return get_object_or_404(qs, project=project, number=number)


def _save_files(ticket, files, user, comment=None, internal=False):
    for f in files:
        Attachment.objects.create(ticket=ticket, comment=comment, file=f, name=f.name, size=f.size,
                                  uploaded_by=user, is_internal=internal)
        TicketEvent.objects.create(
            ticket=ticket, user=user, kind=TicketEvent.Kind.ATTACHED, new_value=f.name, is_internal=internal,
        )


def _ticket_list(request, qs, project=None, template="tickets/ticket_list.html"):
    form = TicketFilterForm(request.GET or None, user=request.user, project=project)
    qs = form.apply(qs).select_related("project__company", "assignee", "author", "milestone")
    sort = request.GET.get("sort", "created")
    qs = qs.order_by(*SORTS.get(sort, SORTS["created"]))
    page = Paginator(qs, 50).get_page(request.GET.get("page"))
    params = request.GET.copy()
    params.pop("page", None)
    return render(request, template, {
        "project": project, "filter_form": form, "page": page, "sort": sort, "querystring": params.urlencode(),
    })


@login_required
def project_tickets(request, key):
    project = get_project_for(request.user, key)
    return _ticket_list(request, Ticket.objects.visible_to(request.user).filter(project=project), project)


@digitalia_required
def all_tickets(request):
    return _ticket_list(request, Ticket.objects.all())


@login_required
def ticket_create(request, key):
    user = request.user
    project = get_project_for(user, key)
    form_class = StaffTicketForm if user.is_digitalia else ClientTicketForm
    initial = {}
    if user.is_digitalia:
        initial = {"visibility": Ticket.Visibility.INTERNAL, "status": Ticket.Status.TODO, "type": Ticket.Type.TASK}
        parent_number = request.GET.get("parent")
        if parent_number and parent_number.isdigit():
            parent = project.tickets.filter(number=parent_number, parent__isnull=True).first()
            if parent:
                initial.update(parent=parent, milestone=parent.milestone, visibility=parent.visibility)
    form = form_class(request.POST or None, request.FILES or None, project=project, initial=initial)
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            ticket = form.save(commit=False)
            ticket.project = project
            ticket.author = user
            ticket.save()
            record_creation(ticket, user)
            _save_files(ticket, form.cleaned_data["files"], user, internal=ticket.visibility == Ticket.Visibility.INTERNAL)
            notifications.ticket_created(ticket)
        messages.success(request, _("Ticket %(ref)s created.") % {"ref": ticket.reference})
        return redirect(ticket)
    return render(request, "tickets/ticket_form.html", {"project": project, "form": form})


@login_required
def ticket_detail(request, key, number):
    user = request.user
    ticket = _get_ticket(user, key, number)
    form = CommentForm(request.POST or None, request.FILES or None, user=user)
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            internal = user.is_digitalia and form.cleaned_data.get("is_internal", False)
            comment = None
            if form.cleaned_data["body"]:
                comment = form.save(commit=False)
                comment.ticket = ticket
                comment.author = user
                comment.is_internal = internal
                comment.save()
                TicketEvent.objects.create(ticket=ticket, user=user, kind=TicketEvent.Kind.COMMENTED, is_internal=internal)
                if user.is_digitalia or ticket.status != Ticket.Status.WAITING_CLIENT:
                    # When a client answers a waiting ticket, the status change e-mail already carries the message.
                    notifications.comment_added(comment)
            _save_files(ticket, form.cleaned_data["files"], user, comment=comment, internal=internal)
            if not user.is_digitalia and ticket.status == Ticket.Status.WAITING_CLIENT:
                # The client answered: hand the ticket back to Digitalia.
                before = snapshot(ticket)
                ticket.status = Ticket.Status.TO_ANALYSE
                ticket.save()
                record_changes(ticket, before, None)
        messages.success(request, _("Your reply has been added."))
        return redirect(ticket)

    comments = ticket.comments.select_related("author").prefetch_related("attachments")
    attachments = ticket.attachments.filter(comment__isnull=True)
    events = ticket.events.select_related("user")
    subtasks = Ticket.objects.visible_to(user).filter(parent=ticket).select_related("assignee")
    if not user.is_digitalia:
        comments = comments.filter(is_internal=False)
        attachments = attachments.filter(is_internal=False)
        events = events.filter(is_internal=False)
    return render(request, "tickets/ticket_detail.html", {
        "ticket": ticket, "project": ticket.project, "form": form, "comments": comments,
        "attachments": attachments, "events": events, "subtasks": subtasks,
    })


@digitalia_required
def ticket_edit(request, key, number):
    ticket = _get_ticket(request.user, key, number)
    form = StaffTicketForm(request.POST or None, request.FILES or None, instance=ticket, project=ticket.project)
    if request.method == "POST" and form.is_valid():
        before = snapshot(Ticket.objects.get(pk=ticket.pk))
        with transaction.atomic():
            ticket = form.save()
            record_changes(ticket, before, request.user)
            _save_files(ticket, form.cleaned_data["files"], request.user,
                        internal=ticket.visibility == Ticket.Visibility.INTERNAL)
        messages.success(request, _("Ticket updated."))
        return redirect(ticket)
    return render(request, "tickets/ticket_form.html", {"project": ticket.project, "form": form, "ticket": ticket})


@login_required
def attachment_download(request, pk):
    attachment = get_object_or_404(Attachment.objects.select_related("ticket__project"), pk=pk)
    ticket = attachment.ticket
    _get_ticket(request.user, ticket.project.key, ticket.number)  # 404 if the ticket is not visible
    if attachment.is_internal and not request.user.is_digitalia:
        raise PermissionDenied
    return FileResponse(attachment.file.open("rb"), as_attachment=not attachment.is_media, filename=attachment.filename)
