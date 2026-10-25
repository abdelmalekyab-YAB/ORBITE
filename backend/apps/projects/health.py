"""Santé d'un projet (règle 23) — calcul, jamais stocké."""
from django.utils import timezone


def project_health(tickets) -> dict:
    """`tickets` : queryset déjà filtré par le périmètre de l'utilisateur (sans internes pour un client)."""
    open_qs = tickets.filter(status__is_closed=False)
    late = open_qs.filter(due_on__lt=timezone.localdate()).count()
    new = open_qs.filter(status__key="nouveau").count()
    waiting = open_qs.filter(status__key="attente").count()
    if late:
        return {"health": "late", "reason": f"{late} demande{'s' if late > 1 else ''} en retard"}
    if new >= 2 or waiting >= 1:
        parts = []
        if new >= 2:
            parts.append(f"{new} nouvelles demandes à qualifier")
        if waiting:
            parts.append(f"{waiting} en attente de réponse client")
        return {"health": "watch", "reason": " · ".join(parts)}
    return {"health": "ok", "reason": "Tout avance comme prévu"}
