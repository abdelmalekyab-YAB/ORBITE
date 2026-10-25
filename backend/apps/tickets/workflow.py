"""Service de workflow (docs/03-workflow.md). Aucune écriture directe de `ticket.status` ailleurs qu'ici."""
from django.db import transaction as db_transaction
from django.utils import timezone
from rest_framework import status
from rest_framework.exceptions import APIException, PermissionDenied

from apps.notifications import service as notifications
from apps.projects.models import Project, WorkflowStatus

from .models import Attachment, Comment, Ticket, TicketEvent


class TransitionNotAllowed(APIException):
    status_code = status.HTTP_409_CONFLICT
    default_detail = "Transition non autorisée par le workflow."
    default_code = "transition_not_allowed"


class BusinessError(APIException):
    status_code = status.HTTP_400_BAD_REQUEST
    default_code = "invalid"

    def __init__(self, detail: str, code: str):
        super().__init__(detail, code)


# Transitions qui exigent un motif (règle 10) → type de commentaire créé.
REASON_REQUIRED = {("test", "cours"): Comment.Kind.REFUSAL, ("termine", "cours"): Comment.Kind.REOPEN,
                   ("devis", "refuse"): Comment.Kind.QUOTE_REFUSAL}
# Actions rapides autorisées à un client (03-workflow.md). Devis : Sprint 2 via /quote/accept|refuse.
CLIENT_TRANSITIONS = {("test", "termine"), ("test", "cours"), ("termine", "cours"), ("attente", "cours")}
MIN_REASON_LENGTH = 10


def status_by_key(project: Project, key: str) -> WorkflowStatus:
    st = WorkflowStatus.for_project(project).filter(key=key).first()
    if st is None:
        raise BusinessError(f"Statut inconnu : {key}", "unknown_status")
    return st


def allowed_next(ticket: Ticket, actor) -> list[str]:
    keys = [s.key for s in ticket.status.next.all()]
    if actor.is_digitalia:
        return keys
    return [k for k in keys if (ticket.status.key, k) in CLIENT_TRANSITIONS]


def validate_reason(body: str | None, attachments) -> None:
    """Règle 10 : ≥ 10 caractères de texte, ou au moins une pièce jointe audio/vidéo."""
    has_media = any((getattr(f, "content_type", "") or "").startswith(("audio/", "video/")) for f in attachments or [])
    if len((body or "").strip()) >= MIN_REASON_LENGTH or has_media:
        return
    raise BusinessError("Merci d'expliquer ce qui ne va pas (10 caractères minimum) "
                        "ou de joindre un message vocal ou une vidéo.", "reason_required")


def check_billing(ticket: Ticket, target_key: str) -> None:
    """Règle 14 : une évolution / fonctionnalité ne se planifie qu'avec une facturation décidée, et « sur devis »
    seulement après l'accord du client. Vaut pour le triage, les boutons rapides et le kanban."""
    if target_key != "faire" or ticket.type not in (Ticket.Type.EVOLUTION, Ticket.Type.FEATURE):
        return
    if ticket.billing not in (Ticket.Billing.LICENCE, Ticket.Billing.QUOTE):
        raise BusinessError("Précisez la facturation (incluse dans la licence ou sur devis) avant de planifier.",
                            "billing_required")
    quote = getattr(ticket, "quote", None) if hasattr(ticket, "quote") else None
    if ticket.billing == Ticket.Billing.QUOTE and not (quote and quote.status == "accepted"):
        raise BusinessError("Une évolution sur devis se planifie après l'accord du client : envoyez la proposition.",
                            "quote_required")


def log(ticket: Ticket, actor, kind: str, from_value="", to_value="", message="") -> TicketEvent:
    return TicketEvent.objects.create(ticket=ticket, actor=actor, kind=kind, from_value=from_value or "",
                                      to_value=to_value or "", message=message)


def update_fields(ticket: Ticket, actor, changes: dict) -> Ticket:
    """Modifie des champs de pilotage (jamais le statut) et journalise chaque changement."""
    if changes.get("type") == Ticket.Type.INTERNAL:
        changes["is_internal"] = True
    changes.pop("status", None)
    dirty = False
    for field, new in changes.items():
        old = getattr(ticket, field)
        if old == new:
            continue
        setattr(ticket, field, new)
        dirty = True
        log(ticket, actor, "assignee" if field == "assignee" else "field",
            str(old) if old is not None else "", str(new) if new is not None else "", message=field)
    if dirty:
        ticket.save()
    return ticket


def add_attachments(ticket: Ticket, files, user, comment: Comment | None = None) -> list[Attachment]:
    return [Attachment.objects.create(ticket=ticket, comment=comment, file=f, name=f.name[:200], uploaded_by=user,
                                      content_type=getattr(f, "content_type", "") or "") for f in files or []]


def add_comment(ticket: Ticket, author, body: str, *, kind=Comment.Kind.COMMENT, attachments=None) -> Comment:
    comment = Comment.objects.create(ticket=ticket, author=author, body=body or "", kind=kind)
    add_attachments(ticket, attachments, author, comment)
    log(ticket, author, "comment", to_value=kind, message=(body or "")[:280])
    return comment


@db_transaction.atomic
def transition(ticket: Ticket, to_status_key: str, actor, *, comment: str | None = None, attachments=None,
               force: bool = False) -> Ticket:
    ticket = Ticket.objects.select_for_update().select_related("status", "project").get(pk=ticket.pk)
    source = ticket.status
    target = status_by_key(ticket.project, to_status_key)
    pair = (source.key, target.key)
    if not force:
        if not source.next.filter(pk=target.pk).exists():
            raise TransitionNotAllowed(f"Impossible de passer de « {source.label} » à « {target.label} ».")
        if not actor.is_digitalia and pair not in CLIENT_TRANSITIONS:
            raise PermissionDenied("Cette action est réservée à l'équipe Digitalia.")
        check_billing(ticket, target.key)
    # Le motif est exigé des décisions du client (« Pas OK », « Rouvrir », refus de proposition) ;
    # « Reprendre » côté Digitalia (test → cours) reste libre.
    reason_kind = None if actor.is_digitalia else REASON_REQUIRED.get(pair)
    if reason_kind:
        validate_reason(comment, attachments)

    ticket.status = target
    ticket.closed_at = timezone.now() if target.is_closed else None
    ticket.save(update_fields=["status", "closed_at", "updated_at"])
    log(ticket, actor, "status", source.key, target.key, f"{source.label} → {target.label}")
    if comment or attachments:
        add_comment(ticket, actor, comment or "", kind=reason_kind or Comment.Kind.COMMENT, attachments=attachments)
    notifications.on_status_changed(ticket, source.key, target.key, actor)
    return ticket


@db_transaction.atomic
def create_ticket(*, project: Project, author, status_key: str, attachments=None, **fields) -> Ticket:
    """Crée un ticket avec numéro séquentiel par projet, jamais réutilisé (règle 6)."""
    locked = Project.objects.select_for_update().get(pk=project.pk)
    locked.ticket_seq += 1
    locked.save(update_fields=["ticket_seq"])
    ticket = Ticket.objects.create(project=locked, number=locked.ticket_seq, author=author,
                                   status=status_by_key(locked, status_key), **fields)
    add_attachments(ticket, attachments, author)
    log(ticket, author, "created", to_value=status_key, message="a créé la demande")
    notifications.on_ticket_created(ticket, author)
    return ticket
