"""Périmètre de visibilité (règles 1-3). Toute requête de liste passe par ces fonctions."""
from .models import Project


def visible_projects(user, include_archived=False):
    qs = Project.objects.select_related("client", "lead")
    if not user.is_digitalia:
        # Un client ne voit que les projets ouverts pour lui ET appartenant à son organisation.
        qs = qs.filter(access__user=user, client=user.organization_id)
    if not include_archived:
        qs = qs.filter(is_archived=False)
    return qs.distinct()


def can_see_project(user, project) -> bool:
    return user.is_digitalia or visible_projects(user).filter(pk=project.pk).exists()
