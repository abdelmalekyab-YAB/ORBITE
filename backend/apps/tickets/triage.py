"""Triage (règles 13-14) : qualifier une demande nouvelle ou en analyse et décider de la suite."""
from django.db import transaction as db_transaction

from . import quotes, workflow
from .models import Ticket
from .workflow import BusinessError, TransitionNotAllowed

TRIAGE_STATUSES = ("nouveau", "analyser")
DECISIONS = ("faire", "analyser", "attente", "refuse", "devis")


@db_transaction.atomic
def triage(ticket: Ticket, actor, *, decision: str, changes: dict, message: str = "", quote: dict | None = None,
           pdf=None) -> Ticket:
    if decision not in DECISIONS:
        raise BusinessError("Décision de triage inconnue.", "invalid_decision")
    # « Modifier la proposition » repasse par le triage : un ticket en devis peut être re-qualifié.
    if ticket.status.key not in (*TRIAGE_STATUSES, "devis"):
        raise TransitionNotAllowed("Cette demande n'est plus à qualifier.")

    if decision == "devis":
        changes["billing"] = Ticket.Billing.QUOTE
    workflow.update_fields(ticket, actor, changes)

    if decision == "faire":
        workflow.check_billing(ticket, "faire")

    if message.strip():
        workflow.add_comment(ticket, actor, message.strip())

    if decision == "devis":
        q = quote or {}
        quotes.send_quote(ticket, actor, amount_ht=q.get("amount_ht"), parts=q.get("parts"),
                          description=q.get("description"), pdf=pdf)
    elif ticket.status.key != decision:
        workflow.transition(ticket, decision, actor, force=True)
    return ticket
