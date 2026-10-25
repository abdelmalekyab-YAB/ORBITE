"""Règle 1 : un client ne voit que les tickets de ses projets ET non internes.
Appliqué ici, dans le queryset, jamais seulement au front."""
from apps.projects.scope import visible_projects

from .models import Ticket


def visible_tickets(user):
    qs = Ticket.objects.select_related("project", "project__client", "status", "author", "assignee", "milestone",
                                       "parent", "parent__project", "quote")
    if user.is_digitalia:
        return qs
    return qs.filter(is_internal=False, project__in=visible_projects(user))
