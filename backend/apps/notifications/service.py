"""Qui prévenir, et quand (règles 24 à 26). Appelé par les services tickets / devis ; l'envoi est asynchrone."""
import threading
from contextlib import contextmanager

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from apps.accounts.models import User

from .models import Notification, NotificationSetting

K = Notification.Kind

# Statut d'arrivée → notification client (règle 24). « nouveau → faire » = planifiée (plus précis que qualifiée).
STATUS_TO_CLIENT_KIND = {"faire": K.PLANNED, "attente": K.INFO_REQUESTED, "test": K.READY_TO_TEST,
                         "termine": K.DELIVERED}
SETTING_OF: dict[str, str] = {
    K.QUALIFIED: "client_qualified", K.PLANNED: "client_planned", K.INFO_REQUESTED: "client_info_requested",
    K.READY_TO_TEST: "client_ready_to_test", K.QUOTE_SENT: "client_quote_sent", K.DELIVERED: "client_delivered",
    K.REMINDER: "client_reminder", K.NEW_REQUEST: "dig_new_request", K.CLIENT_REPLIED: "dig_client_replied",
    K.CLIENT_TESTED: "dig_client_tested", K.QUOTE_DECIDED: "dig_quote_decided", K.DIGEST: "dig_daily_digest",
}
SUBJECTS: dict[str, str] = {
    K.QUALIFIED: "Votre demande {ref} a été prise en charge",
    K.PLANNED: "Votre demande {ref} est planifiée",
    K.INFO_REQUESTED: "Digitalia a besoin d'une précision sur {ref}",
    K.READY_TO_TEST: "{ref} est prête à tester",
    K.QUOTE_SENT: "Une proposition commerciale vous attend ({ref})",
    K.DELIVERED: "{ref} est livrée",
    K.REMINDER: "Rappel : {ref} attend votre retour",
    K.NEW_REQUEST: "Nouvelle demande {ref}",
    K.CLIENT_REPLIED: "Le client a répondu sur {ref}",
    K.CLIENT_TESTED: "Le client a testé {ref}",
    K.QUOTE_DECIDED: "Décision du client sur la proposition {ref}",
}


_state = threading.local()


@contextmanager
def muted():
    """Aucune notification dans ce bloc (chargement des données de démo)."""
    _state.muted = True
    try:
        yield
    finally:
        _state.muted = False


def client_recipients(ticket):
    return User.objects.filter(is_active=True, project_access__project=ticket.project,
                               organization=ticket.project.client_id).distinct()


def team_recipients(ticket, *, include_pm=False, include_assignee=False):
    ids = set()
    if ticket.project.lead_id:
        ids.add(ticket.project.lead_id)
    if include_assignee and ticket.assignee_id:
        ids.add(ticket.assignee_id)
    qs = User.objects.filter(is_active=True, organization__kind="digitalia")
    if include_pm:
        ids |= set(qs.filter(job__in=["pm", "admin"]).values_list("id", flat=True))
    return qs.filter(id__in=ids)


def notify(kind: str, ticket, recipients, *, actor=None, payload: dict | None = None,
           always: bool = False) -> list[Notification]:
    """Crée les notifications et programme les e-mails après commit. Règle 26 : rien sur un ticket interne.
    `always` : ignore le réglage (relance manuelle décidée par Digitalia)."""
    if getattr(_state, "muted", False) or (ticket is not None and ticket.is_internal):
        return []
    if not always and not getattr(NotificationSetting.load(), SETTING_OF[kind]):
        return []
    created = []
    for user in recipients:
        if actor is not None and user.pk == actor.pk:
            continue
        created.append(Notification.objects.create(user=user, ticket=ticket, kind=kind, payload=payload or {}))
    if created:
        ids = [n.id for n in created]
        from .tasks import send_notifications

        transaction.on_commit(lambda: send_notifications.delay(ids))
    return created


# ---------- Crochets appelés par les services métier ----------

def on_ticket_created(ticket, actor):
    if not actor.is_digitalia:
        notify(K.NEW_REQUEST, ticket, team_recipients(ticket, include_pm=True), actor=actor)


def on_status_changed(ticket, source_key: str, target_key: str, actor):
    # Côté client : tous les utilisateurs ayant accès, sauf l'auteur de l'action (ses collègues sont prévenus).
    kind = STATUS_TO_CLIENT_KIND.get(target_key)
    if kind is None and source_key == "nouveau" and target_key not in ("refuse", "annule", "devis"):
        kind = K.QUALIFIED
    if kind:
        payload = {"due_on": str(ticket.due_on) if ticket.due_on else None,
                   "milestone": ticket.milestone.name if ticket.milestone_id else None}
        notify(kind, ticket, client_recipients(ticket), actor=actor, payload=payload)
    if not actor.is_digitalia and source_key == "test":
        notify(K.CLIENT_TESTED, ticket, team_recipients(ticket, include_assignee=True), actor=actor,
               payload={"ok": target_key == "termine"})


def on_client_comment(ticket, actor):
    if not actor.is_digitalia:
        notify(K.CLIENT_REPLIED, ticket, team_recipients(ticket, include_assignee=True), actor=actor)


def on_quote_sent(ticket, actor):
    notify(K.QUOTE_SENT, ticket, client_recipients(ticket), actor=actor,
           payload={"amount_ht": str(ticket.quote.amount_ht)})


def on_quote_decided(ticket, actor, accepted: bool):
    notify(K.QUOTE_DECIDED, ticket, team_recipients(ticket, include_pm=True), actor=actor,
           payload={"accepted": accepted})


def on_ping(ticket, actor):
    notify(K.REMINDER, ticket, client_recipients(ticket), actor=actor, payload={"manual": True}, always=True)


def render_email(n: Notification) -> tuple[str, str]:
    ticket = n.ticket
    if n.kind == K.DIGEST:
        lines = "\n".join(f"- {r['ref']} · {r['title']} ({r['project']})" for r in n.payload.get("tickets", []))
        return (f"Orbit · {len(n.payload.get('tickets', []))} nouvelle(s) demande(s) depuis hier",
                f"Bonjour {n.user.first_name},\n\nNouvelles demandes des dernières 24 h :\n{lines}\n\n"
                f"{settings.FRONTEND_URL}/dig/triage\n")
    assert ticket is not None  # seules les notifications « digest » n'ont pas de ticket
    subject = SUBJECTS[n.kind].format(ref=ticket.ref)
    link = f"{settings.FRONTEND_URL}/{'dig/projets/' + ticket.project.key if n.user.is_digitalia else 'app'}"
    extra = ""
    if n.kind == K.PLANNED and n.payload.get("due_on"):
        extra = f"\nLivraison prévue le {n.payload['due_on']}"
        if n.payload.get("milestone"):
            extra += f" ({n.payload['milestone']})"
    body = (f"Bonjour {n.user.first_name},\n\n{subject}.\n« {ticket.title} » — {ticket.project.name}{extra}\n\n"
            f"Ouvrir Orbit : {link}\n\n— L'équipe Digitalia")
    return f"Orbit · {subject}", body


def mark_sent(ids):
    Notification.objects.filter(id__in=ids).update(sent_at=timezone.now())
