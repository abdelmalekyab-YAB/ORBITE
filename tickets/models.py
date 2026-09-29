import os
import uuid

from django.conf import settings
from django.db import models, transaction
from django.db.models import Max, Q
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from core.models import Milestone, Project


class TicketQuerySet(models.QuerySet):
    def visible_to(self, user):
        if user.is_digitalia:
            return self
        return self.filter(project__members=user, visibility=Ticket.Visibility.CLIENT)

    def open(self):
        return self.exclude(status__in=Ticket.CLOSED_STATUSES)

    def late(self):
        return self.open().filter(due_date__lt=timezone.localdate())


class Ticket(models.Model):
    class Type(models.TextChoices):
        EVOLUTION = "evolution", _("Change request")
        BUG = "bug", _("Bug / anomaly")
        QUESTION = "question", _("Question")
        SUPPORT = "support", _("Support request")
        FEATURE = "feature", _("New feature")
        TASK = "task", _("Internal task")

    class Status(models.TextChoices):
        NEW = "new", _("New")
        TO_ANALYSE = "to_analyse", _("To analyse")
        TODO = "todo", _("To do")
        IN_PROGRESS = "in_progress", _("In progress")
        WAITING_CLIENT = "waiting_client", _("Waiting for client")
        IN_TEST = "in_test", _("In test")
        DONE = "done", _("Done")
        REJECTED = "rejected", _("Rejected")
        CANCELLED = "cancelled", _("Cancelled")

    class Priority(models.TextChoices):
        LOW = "low", _("Low")
        NORMAL = "normal", _("Normal")
        HIGH = "high", _("High")
        CRITICAL = "critical", _("Critical")

    class Origin(models.TextChoices):
        CLIENT = "client", _("Client")
        DIGITALIA = "digitalia", _("Digitalia")
        SYSTEM = "system", _("System")

    class Visibility(models.TextChoices):
        CLIENT = "client", _("Visible to client")
        INTERNAL = "internal", _("Internal Digitalia")

    CLOSED_STATUSES = (Status.DONE, Status.REJECTED, Status.CANCELLED)
    CLIENT_TYPES = (Type.EVOLUTION, Type.BUG, Type.QUESTION, Type.SUPPORT, Type.FEATURE)
    # Fields whose changes are recorded in the ticket history.
    TRACKED_FIELDS = (
        "title", "description", "type", "status", "priority", "visibility",
        "assignee", "milestone", "due_date", "parent",
    )

    project = models.ForeignKey(Project, verbose_name=_("project"), on_delete=models.CASCADE, related_name="tickets")
    number = models.PositiveIntegerField(_("number"), editable=False)
    parent = models.ForeignKey(
        "self", verbose_name=_("parent ticket"), on_delete=models.CASCADE,
        null=True, blank=True, related_name="subtasks",
    )
    milestone = models.ForeignKey(
        Milestone, verbose_name=_("roadmap step"), on_delete=models.SET_NULL,
        null=True, blank=True, related_name="tickets",
    )
    title = models.CharField(_("title"), max_length=200)
    description = models.TextField(_("description"), blank=True)
    type = models.CharField(_("type"), max_length=12, choices=Type.choices, default=Type.EVOLUTION)
    status = models.CharField(_("status"), max_length=16, choices=Status.choices, default=Status.NEW)
    priority = models.CharField(_("priority"), max_length=10, choices=Priority.choices, default=Priority.NORMAL)
    origin = models.CharField(_("origin"), max_length=10, choices=Origin.choices, editable=False)
    visibility = models.CharField(_("visibility"), max_length=10, choices=Visibility.choices, default=Visibility.CLIENT)
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL, verbose_name=_("author"), on_delete=models.SET_NULL,
        null=True, related_name="authored_tickets", editable=False,
    )
    author_company = models.ForeignKey(
        "core.Company", verbose_name=_("author company"), on_delete=models.SET_NULL,
        null=True, blank=True, editable=False, related_name="+",
    )
    assignee = models.ForeignKey(
        settings.AUTH_USER_MODEL, verbose_name=_("assignee"), on_delete=models.SET_NULL,
        null=True, blank=True, related_name="assigned_tickets",
        limit_choices_to=Q(role="staff") | Q(is_superuser=True),
    )
    due_date = models.DateField(_("target date"), null=True, blank=True)
    created_at = models.DateTimeField(_("created at"), auto_now_add=True)
    updated_at = models.DateTimeField(_("updated at"), auto_now=True)
    closed_at = models.DateTimeField(_("closed at"), null=True, blank=True, editable=False)

    objects = TicketQuerySet.as_manager()

    class Meta:
        ordering = ["-created_at"]
        constraints = [models.UniqueConstraint(fields=["project", "number"], name="unique_ticket_number")]
        verbose_name = _("ticket")
        verbose_name_plural = _("tickets")

    def __str__(self):
        return f"{self.reference} {self.title}"

    @property
    def reference(self):
        return f"{self.project.key}-{self.number}"

    @property
    def is_closed(self):
        return self.status in self.CLOSED_STATUSES

    @property
    def is_late(self):
        return bool(self.due_date and not self.is_closed and self.due_date < timezone.localdate())

    def get_absolute_url(self):
        return reverse("ticket_detail", args=[self.project.key, self.number])

    def save(self, *args, **kwargs):
        if self.author_id and not self.author_company_id:
            self.author_company = self.author.company
        if not self.origin:
            if self.author is None:
                self.origin = self.Origin.SYSTEM
            elif self.author.is_digitalia:
                self.origin = self.Origin.DIGITALIA
            else:
                self.origin = self.Origin.CLIENT
        if self.origin == self.Origin.CLIENT:
            # Client requests are always visible to the client.
            self.visibility = self.Visibility.CLIENT
        if self.is_closed and not self.closed_at:
            self.closed_at = timezone.now()
        elif not self.is_closed:
            self.closed_at = None
        if not self.number:
            with transaction.atomic():
                # Lock the project row so concurrent creations get distinct numbers.
                Project.objects.select_for_update().get(pk=self.project_id)
                last = Ticket.objects.filter(project_id=self.project_id).aggregate(m=Max("number"))["m"]
                self.number = (last or 0) + 1
                super().save(*args, **kwargs)
            return
        super().save(*args, **kwargs)


class Comment(models.Model):
    ticket = models.ForeignKey(Ticket, verbose_name=_("ticket"), on_delete=models.CASCADE, related_name="comments")
    author = models.ForeignKey(settings.AUTH_USER_MODEL, verbose_name=_("author"), on_delete=models.SET_NULL, null=True)
    body = models.TextField(_("comment"))
    is_internal = models.BooleanField(
        _("internal note"), default=False, help_text=_("Internal notes are never shown to the client."),
    )
    created_at = models.DateTimeField(_("created at"), auto_now_add=True)

    class Meta:
        ordering = ["created_at"]
        verbose_name = _("comment")
        verbose_name_plural = _("comments")


def attachment_path(instance, filename):
    # A random prefix keeps two files with the same name (e.g. two voice notes) apart.
    return f"attachments/{instance.ticket.project.key}/{instance.ticket.number}/{uuid.uuid4().hex[:8]}-{filename}"


class Attachment(models.Model):
    ticket = models.ForeignKey(Ticket, verbose_name=_("ticket"), on_delete=models.CASCADE, related_name="attachments")
    comment = models.ForeignKey(
        Comment, verbose_name=_("comment"), on_delete=models.CASCADE, null=True, blank=True, related_name="attachments",
    )
    file = models.FileField(_("file"), upload_to=attachment_path)
    name = models.CharField(_("file name"), max_length=255, blank=True)
    size = models.PositiveBigIntegerField(_("size"), default=0)
    uploaded_by = models.ForeignKey(settings.AUTH_USER_MODEL, verbose_name=_("uploaded by"), on_delete=models.SET_NULL, null=True)
    is_internal = models.BooleanField(_("internal"), default=False)
    created_at = models.DateTimeField(_("created at"), auto_now_add=True)

    class Meta:
        ordering = ["created_at"]
        verbose_name = _("attachment")
        verbose_name_plural = _("attachments")

    def save(self, *args, **kwargs):
        if self.file and not self.name:
            self.name = os.path.basename(self.file.name)
        if self.file and not self.size:
            self.size = self.file.size
        super().save(*args, **kwargs)

    @property
    def filename(self):
        return self.name or os.path.basename(self.file.name)

    @property
    def kind(self):
        from .media import kind_for

        return kind_for(self.filename)

    @property
    def is_image(self):
        return self.kind == "image"

    @property
    def is_media(self):
        """Shown inline in the browser rather than downloaded."""
        return self.kind in ("image", "video", "audio") or self.filename.lower().endswith(".pdf")


class TicketEvent(models.Model):
    """One entry of a ticket's history."""

    class Kind(models.TextChoices):
        CREATED = "created", _("Created")
        CHANGED = "changed", _("Changed")
        COMMENTED = "commented", _("Commented")
        ATTACHED = "attached", _("File added")

    ticket = models.ForeignKey(Ticket, verbose_name=_("ticket"), on_delete=models.CASCADE, related_name="events")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, verbose_name=_("user"), on_delete=models.SET_NULL, null=True)
    kind = models.CharField(_("kind"), max_length=10, choices=Kind.choices)
    field = models.CharField(_("field"), max_length=50, blank=True)
    old_value = models.TextField(_("old value"), blank=True)
    new_value = models.TextField(_("new value"), blank=True)
    is_internal = models.BooleanField(_("internal"), default=False)
    created_at = models.DateTimeField(_("date"), auto_now_add=True)

    class Meta:
        ordering = ["created_at", "id"]
        verbose_name = _("history entry")
        verbose_name_plural = _("history")

    @property
    def field_label(self):
        try:
            return Ticket._meta.get_field(self.field).verbose_name
        except Exception:
            return self.field
