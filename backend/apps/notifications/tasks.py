"""Tâches Celery : e-mails transactionnels, rappel client, digest quotidien (Sprint 4)."""
from datetime import timedelta

from celery import shared_task
from django.conf import settings
from django.core.mail import send_mail
from django.utils import timezone

from apps.accounts.models import User

from .models import Notification, NotificationSetting


@shared_task
def send_email(to: str, subject: str, body: str) -> None:
    send_mail(subject, body, settings.DEFAULT_FROM_EMAIL, [to])


@shared_task
def send_notifications(ids: list[int]) -> int:
    from .service import mark_sent, render_email

    sent = []
    for n in Notification.objects.filter(id__in=ids, sent_at__isnull=True).select_related("user", "ticket__project"):
        subject, body = render_email(n)
        send_mail(subject, body, settings.DEFAULT_FROM_EMAIL, [n.user.email])
        sent.append(n.id)
    mark_sent(sent)
    return len(sent)


@shared_task
def remind_waiting_clients() -> int:
    """Règle 24 : rappel au client après N jours sans réponse quand la balle est chez lui (une fois par attente)."""
    from apps.tickets.models import Ticket, TicketEvent

    from .service import K, client_recipients, notify

    setting = NotificationSetting.load()
    if not setting.client_reminder:
        return 0
    threshold = timezone.now() - timedelta(days=setting.reminder_days)
    count = 0
    waiting = Ticket.objects.filter(status__ball="client", status__is_closed=False, is_internal=False)
    for t in waiting.select_related("project", "status"):
        since = (TicketEvent.objects.filter(ticket=t, kind="status", to_value=t.status.key).order_by("-at")
                 .values_list("at", flat=True).first()) or t.created_at
        if since > threshold:
            continue
        if Notification.objects.filter(ticket=t, kind=K.REMINDER, created_at__gte=since).exists():
            continue
        count += len(notify(K.REMINDER, t, client_recipients(t), payload={"since": since.isoformat()}))
    return count


@shared_task
def daily_digest() -> int:
    """Règle 25 : récapitulatif quotidien des nouvelles demandes pour les pm / admin."""
    from apps.tickets.models import Ticket

    from .service import K, notify

    since = timezone.now() - timedelta(days=1)
    fresh = Ticket.objects.filter(created_at__gte=since, is_internal=False, origin="client").select_related("project")
    if not fresh.exists():
        return 0
    payload = {"tickets": [{"ref": t.ref, "title": t.title, "project": t.project.name} for t in fresh]}
    team = User.objects.filter(is_active=True, organization__kind="digitalia", job__in=["pm", "admin"])
    return len(notify(K.DIGEST, None, team, payload=payload))
