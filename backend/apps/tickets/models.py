"""Tickets, discussion, pièces jointes et historique — voir docs/02-modele-de-donnees.md."""
from django.conf import settings
from django.db import models
from django.utils import timezone


class Ticket(models.Model):
    class Type(models.TextChoices):
        BUG = "bug", "Bug / anomalie"
        EVOLUTION = "evolution", "Demande d'évolution"
        FEATURE = "feature", "Nouvelle fonctionnalité"
        QUESTION = "question", "Question"
        SUPPORT = "support", "Demande de support"
        INTERNAL = "internal", "Tâche interne"

    class Priority(models.TextChoices):
        LOW = "low", "Basse"
        NORMAL = "normal", "Normale"
        HIGH = "high", "Haute"
        CRITICAL = "critical", "Critique"

    class Origin(models.TextChoices):
        CLIENT = "client", "Client"
        DIGITALIA = "digitalia", "Digitalia"

    class Billing(models.TextChoices):
        LICENCE = "licence", "Inclus dans la licence"
        QUOTE = "quote", "Sur devis"

    project = models.ForeignKey("projects.Project", on_delete=models.PROTECT, related_name="tickets")
    number = models.PositiveIntegerField()
    type = models.CharField(max_length=12, choices=Type.choices)
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    status = models.ForeignKey("projects.WorkflowStatus", on_delete=models.PROTECT, related_name="tickets")
    priority = models.CharField(max_length=10, choices=Priority.choices, default=Priority.NORMAL)
    origin = models.CharField(max_length=10, choices=Origin.choices)
    is_internal = models.BooleanField(default=False)
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="authored_tickets")
    assignee = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
                                 related_name="assigned_tickets")
    milestone = models.ForeignKey("projects.Milestone", null=True, blank=True, on_delete=models.SET_NULL,
                                  related_name="tickets")
    due_on = models.DateField(null=True, blank=True)
    parent = models.ForeignKey("self", null=True, blank=True, on_delete=models.CASCADE, related_name="children")
    billing = models.CharField(max_length=10, choices=Billing.choices, null=True, blank=True)
    estimate_days = models.DecimalField(max_digits=5, decimal_places=1, null=True, blank=True)
    closed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at"]
        constraints = [models.UniqueConstraint(fields=["project", "number"], name="unique_ticket_number")]
        indexes = [models.Index(fields=["project", "status"]), models.Index(fields=["assignee"]),
                   models.Index(fields=["due_on"])]

    def __str__(self):
        return self.ref

    @property
    def ref(self) -> str:
        return f"{self.project.key}-{self.number}"

    @property
    def is_late(self) -> bool:
        """Règle 12 : date cible dépassée et ticket non clôturé (calcul, pas un statut)."""
        return bool(self.due_on and not self.status.is_closed and self.due_on < timezone.localdate())


class Comment(models.Model):
    class Kind(models.TextChoices):
        COMMENT = "comment", "Commentaire"
        REFUSAL = "refusal", "Refus du test"
        QUOTE_REFUSAL = "quote_refusal", "Refus de la proposition"
        REOPEN = "reopen", "Réouverture"
        PING = "ping", "Relance"

    ticket = models.ForeignKey(Ticket, on_delete=models.CASCADE, related_name="comments")
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="comments")
    body = models.TextField(blank=True)
    kind = models.CharField(max_length=15, choices=Kind.choices, default=Kind.COMMENT)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["created_at"]


def attachment_path(instance, filename):
    return f"tickets/{instance.ticket.project.key}/{instance.ticket.number}/{filename}"


class Attachment(models.Model):
    ticket = models.ForeignKey(Ticket, on_delete=models.CASCADE, related_name="attachments")
    comment = models.ForeignKey(Comment, null=True, blank=True, on_delete=models.CASCADE, related_name="attachments")
    file = models.FileField(upload_to=attachment_path, max_length=300)
    content_type = models.CharField(max_length=120, blank=True)
    name = models.CharField(max_length=200)
    uploaded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    @property
    def is_media(self) -> bool:
        return self.content_type.startswith(("audio/", "video/"))


def quote_path(instance, filename):
    return f"quotes/{instance.ticket.project.key}/{instance.ticket.number}/{filename}"


class Quote(models.Model):
    """Proposition commerciale d'une évolution « sur devis » (règles 14-18)."""

    class Status(models.TextChoices):
        DRAFT = "draft", "Brouillon"
        SENT = "sent", "Envoyée"
        ACCEPTED = "accepted", "Acceptée"
        REFUSED = "refused", "Refusée"

    class Parts(models.IntegerChoices):
        ONE = 1, "En une fois"
        TWO = 2, "50 % / 50 %"
        THREE = 3, "30 % / 40 % / 30 %"

    ticket = models.OneToOneField(Ticket, on_delete=models.CASCADE, related_name="quote")
    amount_ht = models.DecimalField(max_digits=12, decimal_places=2)
    parts = models.PositiveSmallIntegerField(choices=Parts.choices, default=Parts.ONE)
    description = models.TextField(blank=True)
    pdf = models.FileField(upload_to=quote_path, null=True, blank=True, max_length=300)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.DRAFT)
    sent_at = models.DateTimeField(null=True, blank=True)
    decided_at = models.DateTimeField(null=True, blank=True)
    decided_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
                                   related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Devis {self.ticket.ref}"


class QuoteInstallment(models.Model):
    quote = models.ForeignKey(Quote, on_delete=models.CASCADE, related_name="installments")
    due_on = models.DateField()
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    is_paid = models.BooleanField(default=False)
    paid_on = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["due_on", "id"]


class TicketEvent(models.Model):
    ticket = models.ForeignKey(Ticket, on_delete=models.CASCADE, related_name="events")
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
                              related_name="+")
    kind = models.CharField(max_length=20)
    from_value = models.TextField(blank=True)
    to_value = models.TextField(blank=True)
    message = models.TextField(blank=True)
    at = models.DateTimeField(default=timezone.now)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["at", "id"]
