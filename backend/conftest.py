import pytest
from rest_framework.test import APIClient

from apps.accounts.models import User
from tests_support.demo_data import load_demo


@pytest.fixture(autouse=True)
def _media_tmp(settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path / "media"


@pytest.fixture(autouse=True)
def _celery_eager(monkeypatch):
    """Les tâches Celery (e-mails) s'exécutent immédiatement dans les tests, sans broker."""
    from celery.app.task import Task

    monkeypatch.setattr(Task, "delay", lambda self, *args, **kwargs: self.apply(args=args, kwargs=kwargs))


@pytest.fixture
def seeded(db):
    load_demo()


@pytest.fixture
def as_user(seeded):
    """as_user("julie") → APIClient authentifié comme julie@wws.fr (ou @digitalia.io, etc.)."""

    def make(login: str) -> APIClient:
        user = User.objects.get(email__startswith=f"{login}@")
        client = APIClient()
        client.force_authenticate(user)
        client.user = user
        return client

    return make
