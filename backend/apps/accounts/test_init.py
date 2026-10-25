"""Base vide → commande init_orbit : organisation Digitalia + premier admin invité, rien d'autre."""
import io
import re

import pytest
from django.core.management import CommandError, call_command
from rest_framework.test import APIClient

from apps.accounts.models import Organization, User
from apps.projects.models import Project
from apps.tickets.models import Ticket


@pytest.mark.django_db
def test_init_orbit_creates_only_the_admin(mailoutbox, django_capture_on_commit_callbacks):
    out = io.StringIO()
    with django_capture_on_commit_callbacks(execute=True):
        call_command("init_orbit", email="Admin@Digitalia-LTD.com", name="Prénom Nom", stdout=out)
    admin = User.objects.get()
    assert admin.email == "admin@digitalia-ltd.com" and admin.job == "admin" and admin.is_orbit_admin
    assert not admin.has_usable_password()
    assert Organization.objects.count() == 1 and not Project.objects.exists() and not Ticket.objects.exists()
    assert len(mailoutbox) == 1
    m = re.search(r"\?uid=([^&\s]+)&token=(\S+)", out.getvalue())
    r = APIClient().post("/api/v1/auth/invite/accept", {"uid": m.group(1), "token": m.group(2),
                                                        "password": "Orbit-2026!"}, format="json")
    assert r.status_code == 200 and r.data["me"]["is_orbit_admin"] is True
    with pytest.raises(CommandError):
        call_command("init_orbit", email="admin@digitalia-ltd.com", name="Doublon", stdout=io.StringIO())


def accept(out: str, password: str) -> APIClient:
    m = re.search(r"\?uid=([^&\s]+)&token=(\S+)", out)
    r = APIClient().post("/api/v1/auth/invite/accept", {"uid": m.group(1), "token": m.group(2), "password": password},
                         format="json")
    assert r.status_code == 200, r.data
    c = APIClient()
    c.credentials(HTTP_AUTHORIZATION="Bearer " + r.data["access"])
    return c


@pytest.mark.django_db
def test_real_flow_from_an_empty_database(mailoutbox, monkeypatch):
    """Base vide : ce que l'admin crée, ce que le client dépose et le statut changé sont réellement visibles."""
    from django.db import transaction

    monkeypatch.setattr(transaction, "on_commit", lambda func, using=None, robust=False: func())
    out = io.StringIO()
    call_command("init_orbit", email="direction@digitalia-ltd.com", name="Direction Digitalia", stdout=out)
    admin = accept(out.getvalue(), "Orbit-2026!")

    # L'admin crée un client (contact invité) puis un projet
    r = admin.post("/api/v1/organizations", {"name": "Client Réel", "contact_name": "Contact Client",
                                             "contact_email": "contact@client-reel.fr"}, format="json")
    assert r.status_code == 201
    org_id = r.data["id"]
    assert [o["name"] for o in admin.get("/api/v1/organizations").data] == ["Client Réel"]
    r = admin.post("/api/v1/projects", {"key": "CLR", "name": "Portail client", "client": org_id}, format="json")
    assert r.status_code == 201

    # Le contact accepte son invitation (lien reçu par e-mail) et dépose une demande
    invite = next(m for m in mailoutbox if m.to == ["contact@client-reel.fr"])
    client = accept(invite.body, "Client-2026!")
    assert [p["key"] for p in client.get("/api/v1/me").data["projects"]] == ["CLR"]
    r = client.post("/api/v1/tickets", {"project": "CLR", "type": "bug", "title": "Export impossible"}, format="json")
    assert r.status_code == 201 and r.data["ref"] == "CLR-1"
    tid = r.data["id"]

    # Digitalia voit la demande et change son statut ; le client voit le nouveau statut
    assert [t["ref"] for t in admin.get("/api/v1/triage").data] == ["CLR-1"]
    assert admin.post(f"/api/v1/tickets/{tid}/transition", {"to": "analyser"}, format="json").status_code == 200
    seen = client.get(f"/api/v1/tickets/{tid}").data
    assert seen["status"] == "analyser" and seen["client_label"] == "Reçue"
    assert admin.post(f"/api/v1/tickets/{tid}/transition", {"to": "faire"}, format="json").status_code == 200
    assert client.get(f"/api/v1/tickets/{tid}").data["client_label"] == "Planifiée"
    assert Ticket.objects.count() == 1 and Project.objects.count() == 1


@pytest.mark.django_db
def test_empty_database_has_no_business_data():
    """Après migration : uniquement la configuration (workflow par défaut), aucune donnée métier."""
    from apps.finance.models import FinanceSettings
    from apps.projects.models import WorkflowStatus

    assert not User.objects.exists() and not Organization.objects.exists() and not Project.objects.exists()
    assert WorkflowStatus.objects.filter(project__isnull=True).count() == 11
    assert FinanceSettings.load().default_tjm == 0  # à définir par l'admin, pas de valeur inventée
