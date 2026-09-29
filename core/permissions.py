from functools import wraps

from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404

from .models import Project


def digitalia_required(view):
    @wraps(view)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated or not request.user.is_digitalia:
            raise PermissionDenied
        return view(request, *args, **kwargs)

    return wrapper


def get_project_for(user, key):
    """Return the project if the user may access it, else 404 (never reveal other clients' projects)."""
    return get_object_or_404(user.visible_projects().select_related("company"), key__iexact=key)
