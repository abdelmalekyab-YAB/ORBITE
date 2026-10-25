"""Permissions par rôle (règle 3), vérifiées côté API."""
from rest_framework.permissions import BasePermission


class IsDigitalia(BasePermission):
    message = "Réservé à l'équipe Digitalia."

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.is_digitalia)


class IsOrbitAdmin(BasePermission):
    message = "Réservé aux administrateurs Digitalia."

    def has_permission(self, request, view):
        u = request.user
        return bool(u and u.is_authenticated and u.is_orbit_admin)


class IsPmOrAdmin(BasePermission):
    message = "Réservé aux chefs de projet et administrateurs."

    def has_permission(self, request, view):
        u = request.user
        return bool(u and u.is_authenticated and u.is_digitalia and u.job in ("pm", "admin"))
