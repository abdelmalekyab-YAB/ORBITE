from django.contrib.auth.models import AbstractUser
from django.db import models
from django.db.models import Q
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import gettext_lazy as _


class Company(models.Model):
    """A client company, or Digitalia itself (is_internal=True)."""

    name = models.CharField(_("name"), max_length=150, unique=True)
    is_internal = models.BooleanField(
        _("Digitalia (internal)"), default=False,
        help_text=_("Check for Digitalia itself; leave unchecked for clients."),
    )
    created_at = models.DateTimeField(_("created at"), auto_now_add=True)

    class Meta:
        ordering = ["name"]
        verbose_name = _("company")
        verbose_name_plural = _("companies")

    def __str__(self):
        return self.name


class User(AbstractUser):
    class Role(models.TextChoices):
        CLIENT = "client", _("Client")
        STAFF = "staff", _("Digitalia team")

    role = models.CharField(_("role"), max_length=10, choices=Role.choices, default=Role.CLIENT)
    company = models.ForeignKey(
        Company, verbose_name=_("company"), on_delete=models.PROTECT,
        null=True, blank=True, related_name="users",
    )

    class Meta:
        verbose_name = _("user")
        verbose_name_plural = _("users")

    @property
    def is_digitalia(self):
        return self.role == self.Role.STAFF or self.is_superuser

    def visible_projects(self):
        if self.is_digitalia:
            return Project.objects.all()
        return self.projects.all()

    def __str__(self):
        return self.get_full_name() or self.username


class Project(models.Model):
    company = models.ForeignKey(
        Company, verbose_name=_("client"), on_delete=models.PROTECT, related_name="projects",
        limit_choices_to={"is_internal": False},
    )
    name = models.CharField(_("name"), max_length=150)
    key = models.SlugField(
        _("key"), max_length=10, unique=True,
        help_text=_("Short prefix used in ticket references, e.g. SCV."),
    )
    description = models.TextField(_("description"), blank=True)
    members = models.ManyToManyField(
        User, verbose_name=_("client members"), related_name="projects", blank=True,
        help_text=_("Client accounts that can access this project."),
    )
    lead = models.ForeignKey(
        User, verbose_name=_("project lead"), on_delete=models.SET_NULL,
        null=True, blank=True, related_name="led_projects",
        limit_choices_to=Q(role="staff") | Q(is_superuser=True),
    )
    is_active = models.BooleanField(_("active"), default=True)
    created_at = models.DateTimeField(_("created at"), auto_now_add=True)

    class Meta:
        ordering = ["company__name", "name"]
        verbose_name = _("project")
        verbose_name_plural = _("projects")

    def save(self, *args, **kwargs):
        self.key = self.key.upper()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.name} ({self.company})"

    def get_absolute_url(self):
        return reverse("project_detail", args=[self.key])


class Milestone(models.Model):
    """A roadmap step: version, lot, sprint or milestone."""

    class Kind(models.TextChoices):
        VERSION = "version", _("Version")
        LOT = "lot", _("Lot")
        SPRINT = "sprint", _("Sprint")
        MILESTONE = "milestone", _("Milestone")

    class Status(models.TextChoices):
        PLANNED = "planned", _("Planned")
        IN_PROGRESS = "in_progress", _("In progress")
        DONE = "done", _("Done")

    project = models.ForeignKey(Project, verbose_name=_("project"), on_delete=models.CASCADE, related_name="milestones")
    name = models.CharField(_("name"), max_length=150)
    kind = models.CharField(_("kind"), max_length=12, choices=Kind.choices, default=Kind.VERSION)
    status = models.CharField(_("status"), max_length=12, choices=Status.choices, default=Status.PLANNED)
    description = models.TextField(_("description"), blank=True)
    start_date = models.DateField(_("start date"), null=True, blank=True)
    due_date = models.DateField(_("due date"), null=True, blank=True)
    is_client_visible = models.BooleanField(_("visible to client"), default=True)

    class Meta:
        ordering = ["project", "due_date", "id"]
        verbose_name = _("roadmap step")
        verbose_name_plural = _("roadmap steps")

    def __str__(self):
        return f"{self.get_kind_display()} {self.name}"

    @property
    def is_late(self):
        return bool(self.due_date and self.status != self.Status.DONE and self.due_date < timezone.localdate())
