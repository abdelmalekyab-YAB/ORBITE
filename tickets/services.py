"""Business helpers: history tracking and per-project statistics."""
from django.db.models import Count, Q
from django.utils import timezone

from .models import Ticket, TicketEvent

INTERNAL_FIELDS = {"visibility", "parent"}


def _display(ticket, field):
    value = getattr(ticket, field)
    if value is None or value == "":
        return ""
    if hasattr(ticket, f"get_{field}_display"):
        return str(getattr(ticket, f"get_{field}_display")())
    return str(value)


def snapshot(ticket):
    return {field: _display(ticket, field) for field in Ticket.TRACKED_FIELDS}


def record_creation(ticket, user):
    TicketEvent.objects.create(
        ticket=ticket, user=user, kind=TicketEvent.Kind.CREATED,
        is_internal=ticket.visibility == Ticket.Visibility.INTERNAL,
    )


def record_changes(ticket, before, user):
    after = snapshot(ticket)
    events = [
        TicketEvent(
            ticket=ticket, user=user, kind=TicketEvent.Kind.CHANGED, field=field,
            old_value=before[field], new_value=after[field], is_internal=field in INTERNAL_FIELDS,
        )
        for field in Ticket.TRACKED_FIELDS
        if before[field] != after[field]
    ]
    TicketEvent.objects.bulk_create(events)
    if before["status"] != after["status"]:
        from .notifications import status_changed

        labels = {str(label): value for value, label in Ticket.Status.choices}
        status_changed(ticket, labels.get(before["status"]), user)
    return events


def ticket_stats(tickets):
    """Counters used by the dashboards, computed in one query."""
    today = timezone.localdate()
    open_q = ~Q(status__in=Ticket.CLOSED_STATUSES)
    return tickets.aggregate(
        total=Count("id"),
        open=Count("id", filter=open_q),
        bugs=Count("id", filter=open_q & Q(type=Ticket.Type.BUG)),
        evolutions=Count("id", filter=open_q & Q(type__in=[Ticket.Type.EVOLUTION, Ticket.Type.FEATURE])),
        in_progress=Count("id", filter=Q(status__in=[Ticket.Status.IN_PROGRESS, Ticket.Status.IN_TEST])),
        waiting_client=Count("id", filter=Q(status=Ticket.Status.WAITING_CLIENT)),
        late=Count("id", filter=open_q & Q(due_date__lt=today)),
        done=Count("id", filter=Q(status=Ticket.Status.DONE)),
        from_client=Count("id", filter=Q(origin=Ticket.Origin.CLIENT)),
    )


def progress(stats):
    """Percentage of done tickets among tickets that were not rejected/cancelled."""
    relevant = stats["open"] + stats["done"]
    return round(100 * stats["done"] / relevant) if relevant else 0
