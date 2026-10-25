"""Le module Facturation est réservé à l'administration d'Orbit (règle : finances invisibles hors admin)."""

from rest_framework.permissions import BasePermission


class IsFinanceAdmin(BasePermission):
    message = "Le module Finance est réservé à l'administration."

    def has_permission(self, request, view):
        user = request.user
        return bool(user and user.is_authenticated and user.is_active and user.is_orbit_admin)
