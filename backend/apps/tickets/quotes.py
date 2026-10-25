"""Propositions commerciales (docs/04-regles-metier.md, règles 14 à 18)."""
from datetime import timedelta
from decimal import ROUND_HALF_UP, Decimal

from django.db import transaction as db_transaction
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied

from apps.notifications import service as notifications

from . import workflow
from .models import Quote, QuoteInstallment, Ticket
from .workflow import BusinessError

# Répartition des échéances selon le nombre de parts (règle 16).
SPLITS = {1: [100], 2: [50, 50], 3: [30, 40, 30]}
INSTALLMENT_GAP_DAYS = 45
CENT = Decimal("0.01")


def split_amount(amount: Decimal, parts: int) -> list[Decimal]:
    """Montants des échéances ; la dernière absorbe l'arrondi pour que la somme soit exacte."""
    shares = [(amount * pct / 100).quantize(CENT, ROUND_HALF_UP) for pct in SPLITS[parts][:-1]]
    return [*shares, (amount - sum(shares, Decimal("0"))).quantize(CENT)]


def _validate(amount_ht, parts) -> tuple[Decimal, int]:
    try:
        amount = Decimal(str(amount_ht)).quantize(CENT)
    except Exception as exc:
        raise BusinessError("Montant de la proposition invalide.", "invalid_amount") from exc
    if amount <= 0:
        raise BusinessError("La proposition doit avoir un montant supérieur à 0.", "invalid_amount")
    parts = int(parts or 1)
    if parts not in SPLITS:
        raise BusinessError("L'échéancier doit comporter 1, 2 ou 3 parts.", "invalid_parts")
    return amount, parts


@db_transaction.atomic
def send_quote(ticket: Ticket, actor, *, amount_ht=None, parts=None, description=None, pdf=None) -> Quote:
    """Règle 15 : proposition envoyée, ticket → devis (force), événement. Réutilise le brouillon existant."""
    quote = getattr(ticket, "quote", None)
    if quote and quote.status == Quote.Status.ACCEPTED:
        raise BusinessError("Cette proposition a déjà été acceptée.", "quote_accepted")
    amount, n_parts = _validate(amount_ht if amount_ht is not None else getattr(quote, "amount_ht", None),
                                parts if parts is not None else getattr(quote, "parts", 1))
    if quote is None:
        quote = Quote(ticket=ticket)
    quote.amount_ht, quote.parts = amount, n_parts
    if description is not None:
        quote.description = description
    if pdf:
        quote.pdf = pdf
    quote.status, quote.sent_at, quote.decided_at, quote.decided_by = Quote.Status.SENT, timezone.now(), None, None
    quote.save()
    if not pdf and (not quote.pdf or "/proposition-" in (quote.pdf.name or "")):
        # Pas de PDF joint (ou PDF généré précédemment) : on (re)génère la proposition à partir des données.
        from .pdf import attach_generated_pdf

        attach_generated_pdf(quote)
    if ticket.billing != Ticket.Billing.QUOTE:
        workflow.update_fields(ticket, actor, {"billing": Ticket.Billing.QUOTE})
    if ticket.status.key != "devis":
        workflow.transition(ticket, "devis", actor, force=True)
    workflow.log(ticket, actor, "quote_sent", to_value=str(amount),
                 message=f"a envoyé une proposition commerciale ({amount} € HT)")
    notifications.on_quote_sent(ticket, actor)
    return quote


@db_transaction.atomic
def update_quote(quote: Quote, actor, *, amount_ht=None, parts=None, description=None, pdf=None) -> Quote:
    """Règle 18 : une proposition envoyée repasse en brouillon quand Digitalia la modifie."""
    if quote.status not in (Quote.Status.DRAFT, Quote.Status.SENT):
        raise BusinessError("Seule une proposition en attente peut être modifiée.", "quote_locked")
    amount, n_parts = _validate(amount_ht if amount_ht is not None else quote.amount_ht,
                                parts if parts is not None else quote.parts)
    quote.amount_ht, quote.parts = amount, n_parts
    if description is not None:
        quote.description = description
    if pdf:
        quote.pdf = pdf
    quote.status = Quote.Status.DRAFT
    quote.save()
    workflow.log(quote.ticket, actor, "quote_updated", message="a modifié la proposition commerciale")
    return quote


def _decidable(ticket: Ticket, actor) -> Quote:
    if actor.is_digitalia:
        raise PermissionDenied("La décision sur une proposition appartient au client.")
    quote = getattr(ticket, "quote", None)
    if quote is None or quote.status != Quote.Status.SENT:
        raise BusinessError("Aucune proposition en attente de votre décision.", "no_pending_quote")
    return quote


@db_transaction.atomic
def accept_quote(ticket: Ticket, actor) -> Quote:
    """Règle 16 : échéancier 100 / 50-50 / 30-40-30, 1re échéance le jour même puis +45 j ; ticket → faire."""
    quote = _decidable(ticket, actor)
    today = timezone.localdate()
    quote.status, quote.decided_at, quote.decided_by = Quote.Status.ACCEPTED, timezone.now(), actor
    quote.save()
    quote.installments.all().delete()
    for i, amount in enumerate(split_amount(quote.amount_ht, quote.parts)):
        QuoteInstallment.objects.create(quote=quote, amount=amount,
                                        due_on=today + timedelta(days=INSTALLMENT_GAP_DAYS * i))
    workflow.transition(ticket, "faire", actor, force=True)
    workflow.log(ticket, actor, "quote_accepted", to_value=str(quote.amount_ht),
                 message=f"a accepté la proposition commerciale ({quote.amount_ht} € HT)")
    notifications.on_quote_decided(ticket, actor, accepted=True)
    return quote


@db_transaction.atomic
def refuse_quote(ticket: Ticket, actor, *, reason: str | None, attachments=None) -> Quote:
    """Règle 17 : motif obligatoire (règle 10), ticket → refuse."""
    quote = _decidable(ticket, actor)
    workflow.validate_reason(reason, attachments)
    quote.status, quote.decided_at, quote.decided_by = Quote.Status.REFUSED, timezone.now(), actor
    quote.save()
    workflow.transition(ticket, "refuse", actor, comment=reason, attachments=attachments, force=True)
    workflow.log(ticket, actor, "quote_refused", message="a refusé la proposition commerciale")
    notifications.on_quote_decided(ticket, actor, accepted=False)
    return quote
