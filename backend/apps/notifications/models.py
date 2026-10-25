"""Notifications (docs/02-modele-de-donnees.md et règles 24 à 26)."""
from django.conf import settings
from django.db import models


class NotificationSetting(models.Model):
    """Singleton (pk=1) : quels événements déclenchent un e-mail. Réglable par pm/admin."""

    # Côté client (règle 24)
    client_qualified = models.BooleanField(default=True)
    client_planned = models.BooleanField(default=True)
    client_info_requested = models.BooleanField(default=True)
    client_ready_to_test = models.BooleanField(default=True)
    client_quote_sent = models.BooleanField(default=True)
    client_delivered = models.BooleanField(default=True)
    client_reminder = models.BooleanField(default=False)
    reminder_days = models.PositiveSmallIntegerField(default=3)
    # Côté Digitalia (règle 25)
    dig_new_request = models.BooleanField(default=True)
    dig_client_replied = models.BooleanField(default=True)
    dig_client_tested = models.BooleanField(default=True)
    dig_quote_decided = models.BooleanField(default=True)
    dig_daily_digest = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    @classmethod
    def load(cls) -> "NotificationSetting":
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj


class Notification(models.Model):
    class Kind(models.TextChoices):
        QUALIFIED = "qualified", "Demande qualifiée"
        PLANNED = "planned", "Demande planifiée"
        INFO_REQUESTED = "info_requested", "Précision demandée"
        READY_TO_TEST = "ready_to_test", "Prête à tester"
        QUOTE_SENT = "quote_sent", "Proposition envoyée"
        DELIVERED = "delivered", "Demande livrée"
        REMINDER = "reminder", "Rappel"
        NEW_REQUEST = "new_request", "Nouvelle demande"
        CLIENT_REPLIED = "client_replied", "Le client a répondu"
        CLIENT_TESTED = "client_tested", "Le client a testé"
        QUOTE_DECIDED = "quote_decided", "Décision sur un devis"
        DIGEST = "digest", "Récapitulatif quotidien"

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="notifications")
    ticket = models.ForeignKey("tickets.Ticket", null=True, blank=True, on_delete=models.CASCADE,
                               related_name="notifications")
    kind = models.CharField(max_length=20, choices=Kind.choices)
    payload = models.JSONField(default=dict, blank=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    read_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        indexes = [models.Index(fields=["user", "read_at"])]
