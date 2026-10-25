"""Projets, accès clients, versions et workflow configurable — voir docs/02-modele-de-donnees.md et 03-workflow.md."""
from django.conf import settings
from django.db import models


class Project(models.Model):
    key = models.CharField(max_length=6, unique=True)
    name = models.CharField(max_length=120)
    description = models.TextField(blank=True)
    client = models.ForeignKey("accounts.Organization", on_delete=models.PROTECT, related_name="projects")
    lead = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
                             related_name="led_projects")
    is_archived = models.BooleanField(default=False)
    # Dernier numéro de ticket attribué : jamais décrémenté, donc jamais réutilisé (règle 6).
    ticket_seq = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["key"]

    def __str__(self):
        return self.key

    def save(self, *args, **kwargs):
        self.key = self.key.upper()
        super().save(*args, **kwargs)


class ProjectAccess(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="project_access")
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="access")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["user", "project"], name="unique_project_access")]


class Milestone(models.Model):
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="milestones")
    name = models.CharField(max_length=80)
    starts_on = models.DateField(null=True, blank=True)
    ends_on = models.DateField(null=True, blank=True)
    order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["order", "starts_on"]

    def __str__(self):
        return f"{self.project.key} {self.name}"


class WorkflowStatus(models.Model):
    class Ball(models.TextChoices):
        DIGITALIA = "digitalia", "Chez Digitalia"
        CLIENT = "client", "Chez le client"
        NONE = "none", "Aucune"

    project = models.ForeignKey(Project, null=True, blank=True, on_delete=models.CASCADE, related_name="statuses")
    key = models.SlugField(max_length=30)
    label = models.CharField(max_length=60)
    client_label = models.CharField(max_length=60)
    ball = models.CharField(max_length=10, choices=Ball.choices, default=Ball.DIGITALIA)
    is_closed = models.BooleanField(default=False)
    is_terminal_ok = models.BooleanField(default=False)
    order = models.PositiveIntegerField(default=0)
    color = models.CharField(max_length=9, blank=True)
    next = models.ManyToManyField("self", symmetrical=False, blank=True, related_name="previous")
    is_system = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["order"]
        constraints = [models.UniqueConstraint(fields=["project", "key"], name="unique_status_per_project"),
                       models.UniqueConstraint(fields=["key"], condition=models.Q(project__isnull=True),
                                               name="unique_global_status")]

    def __str__(self):
        return self.key

    @classmethod
    def for_project(cls, project):
        """Statuts du projet s'il a personnalisé son workflow, sinon le workflow global."""
        qs = cls.objects.filter(project=project)
        return qs if qs.exists() else cls.objects.filter(project__isnull=True)
