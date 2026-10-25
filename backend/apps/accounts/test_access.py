"""Règles 1 à 5 (accès), écran Accès (admin) et critère du Sprint 4 :
l'admin crée un client, un projet, invite un utilisateur qui se connecte."""
import re

import pytest
from rest_framework.test import APIClient

from apps.accounts.models import Organization, User
from apps.finance.models import ProjectFinance
from apps.projects.models import Project, ProjectAccess


def link_params(body: str) -> dict:
    m = re.search(r"\?uid=([^&\s]+)&token=([^\s]+)", body)
    assert m, body
    return {"uid": m.group(1), "token": m.group(2)}


def login(email, password):
    return APIClient().post("/api/v1/auth/login", {"email": email, "password": password}, format="json")


# ---------- Règle 3 : permissions par rôle vérifiées côté API ----------

@pytest.mark.parametrize("login_name,expected", [("admin", 200), ("yanis", 403), ("sara", 403), ("julie", 403)])
def test_access_screens_are_admin_only(as_user, login_name, expected):
    c = as_user(login_name)
    assert c.get("/api/v1/users").status_code == expected
    assert c.get("/api/v1/organizations").status_code == expected


@pytest.mark.parametrize("login_name,expected", [("admin", 200), ("yanis", 200), ("sara", 403), ("julie", 403)])
def test_settings_are_pm_admin(as_user, login_name, expected):
    assert as_user(login_name).get("/api/v1/settings/notifications").status_code == expected


# ---------- Règle 4 : désactivation, invitation, première connexion ----------

def test_disabled_account_cannot_login(as_user):
    admin = as_user("admin")
    julie = User.objects.get(email="julie@wws.fr")
    assert admin.post(f"/api/v1/users/{julie.id}/deactivate").data["status"] == "disabled"
    r = login("julie@wws.fr", "orbit")
    assert r.status_code == 401 and r.data["code"] == "account_disabled"
    admin.post(f"/api/v1/users/{julie.id}/activate")
    assert login("julie@wws.fr", "orbit").status_code == 200


def test_admin_cannot_deactivate_self(as_user):
    admin = as_user("admin")
    assert admin.post(f"/api/v1/users/{admin.user.id}/deactivate").status_code == 400


def test_invitation_flow(as_user, mailoutbox, django_capture_on_commit_callbacks):
    admin = as_user("admin")
    wws = Organization.objects.get(name="WWS")
    with django_capture_on_commit_callbacks(execute=True):
        r = admin.post("/api/v1/users", {"name": "Paul Durand", "email": "Paul@WWS.fr", "organization": wws.id},
                       format="json")
    assert r.status_code == 201 and r.data["status"] == "invited" and r.data["job"] == "client"
    assert len(mailoutbox) == 1 and mailoutbox[0].to == ["paul@wws.fr"]
    params = link_params(mailoutbox[0].body)

    r = login("paul@wws.fr", "anything")
    assert r.status_code == 401 and r.data["code"] == "invitation_pending"
    weak = APIClient().post("/api/v1/auth/invite/accept", {**params, "password": "123"}, format="json")
    assert weak.status_code == 400 and weak.data["code"] == "weak_password"

    r = APIClient().post("/api/v1/auth/invite/accept", {**params, "password": "Orbit-2026!"}, format="json")
    assert r.status_code == 200 and r.data["me"]["email"] == "paul@wws.fr"
    paul = User.objects.get(email="paul@wws.fr")
    assert paul.activated_at is not None
    again = APIClient().post("/api/v1/auth/invite/accept", {**params, "password": "Other-2026!"}, format="json")
    assert again.status_code == 400 and again.data["code"] == "invalid_link"  # lien à usage unique
    assert login("paul@wws.fr", "Orbit-2026!").status_code == 200


def test_first_login_sets_activated_at(seeded):
    assert User.objects.get(email="marc@rmclub.fr").activated_at is None
    login("marc@rmclub.fr", "orbit")
    assert User.objects.get(email="marc@rmclub.fr").activated_at is not None


def test_forgot_and_reset_password(seeded, mailoutbox, django_capture_on_commit_callbacks):
    with django_capture_on_commit_callbacks(execute=True):
        r = APIClient().post("/api/v1/auth/password/forgot", {"email": "julie@wws.fr"}, format="json")
        unknown = APIClient().post("/api/v1/auth/password/forgot", {"email": "nobody@x.fr"}, format="json")
    assert r.status_code == unknown.status_code == 200 and r.data == unknown.data  # pas d'énumération
    assert len(mailoutbox) == 1
    params = link_params(mailoutbox[0].body)
    r = APIClient().post("/api/v1/auth/password/reset", {**params, "password": "Nouveau-2026!"}, format="json")
    assert r.status_code == 200
    assert login("julie@wws.fr", "orbit").status_code == 401
    assert login("julie@wws.fr", "Nouveau-2026!").status_code == 200


def test_resend_invite_and_reset_password_actions(as_user, mailoutbox, django_capture_on_commit_callbacks):
    admin = as_user("admin")
    with django_capture_on_commit_callbacks(execute=True):
        uid = admin.post("/api/v1/users", {"name": "Léa Dev", "email": "lea@digitalia.io", "job": "dev"},
                         format="json").data["id"]
        assert admin.post(f"/api/v1/users/{uid}/resend-invite").status_code == 200
        julie = User.objects.get(email="julie@wws.fr")
        assert admin.post(f"/api/v1/users/{julie.id}/resend-invite").status_code == 400  # déjà active
        assert admin.post(f"/api/v1/users/{julie.id}/reset-password").status_code == 200
    assert [m.to[0] for m in mailoutbox] == ["lea@digitalia.io", "lea@digitalia.io", "julie@wws.fr"]
    assert User.objects.get(pk=uid).job == "dev" and User.objects.get(pk=uid).is_digitalia


def test_update_user(as_user):
    admin = as_user("admin")
    sara = User.objects.get(email="sara@digitalia.io")
    r = admin.patch(f"/api/v1/users/{sara.id}", {"name": "Sara Martin", "job": "pm"}, format="json")
    assert r.data["name"] == "Sara Martin" and r.data["job"] == "pm"
    assert admin.patch(f"/api/v1/users/{sara.id}", {"email": "julie@wws.fr"}, format="json").status_code == 400
    julie = User.objects.get(email="julie@wws.fr")
    assert admin.patch(f"/api/v1/users/{julie.id}", {"job": "admin"}, format="json").status_code == 400
    assert admin.patch(f"/api/v1/users/{admin.user.id}", {"job": "dev"}, format="json").status_code == 400


def test_duplicate_email_rejected(as_user):
    r = as_user("admin").post("/api/v1/users", {"name": "X", "email": "JULIE@wws.fr", "job": "dev"}, format="json")
    assert r.status_code == 400


# ---------- Règles 1 et 5 : accès par projet, limité à l'organisation ----------

def test_project_access(as_user):
    admin = as_user("admin")
    julie = User.objects.get(email="julie@wws.fr")
    r = admin.put(f"/api/v1/users/{julie.id}/project-access", {"projects": ["CHK"]}, format="json")
    assert r.status_code == 200 and r.data["projects"] == ["CHK"]
    keys = {t["ref"].split("-")[0] for t in as_user("julie").get("/api/v1/tickets").data["results"]}
    assert keys == {"CHK"}
    r = admin.put(f"/api/v1/users/{julie.id}/project-access", {"projects": ["CHK", "RMC"]}, format="json")
    assert r.status_code == 400 and r.data["code"] == "foreign_project"
    admin.put(f"/api/v1/users/{julie.id}/project-access", {"projects": []}, format="json")
    assert as_user("julie").get("/api/v1/me").data["projects"] == []  # règle 5 : écran vide, pas d'erreur


# ---------- Clients et projets ----------

def test_create_project_opens_access_and_finance(as_user):
    admin = as_user("admin")
    wws = Organization.objects.get(name="WWS")
    yanis = User.objects.get(email="yanis@digitalia.io")
    r = admin.post("/api/v1/projects", {"key": "prh", "name": "Portail RH", "client": wws.id, "lead": yanis.id,
                                        "dev_price": "15000", "licence_amount": "600", "licence_start": "2026-11"},
                   format="json")
    assert r.status_code == 201, r.data
    p = Project.objects.get(key="PRH")
    fin = ProjectFinance.objects.get(project=p)
    assert fin.dev_price == 15000 and str(fin.licence_start) == "2026-11-01"
    assert ProjectAccess.objects.filter(project=p, user__email="julie@wws.fr").exists()
    assert admin.post("/api/v1/projects", {"key": "PRH", "name": "x", "client": wws.id}, format="json").status_code == 400
    assert admin.post("/api/v1/projects", {"key": "1X", "name": "x", "client": wws.id}, format="json").status_code == 400
    assert as_user("yanis").post("/api/v1/projects", {"key": "ZZ", "name": "x", "client": wws.id},
                                 format="json").status_code == 403


def test_archive_project_hides_it(as_user):
    admin = as_user("admin")
    assert admin.post("/api/v1/projects/CHK/archive").data["is_archived"] is True
    assert "CHK" not in [p["key"] for p in as_user("julie").get("/api/v1/me").data["projects"]]
    assert "CHK" in [p["key"] for p in admin.get("/api/v1/projects?include_archived=1").data]
    assert admin.post("/api/v1/projects/CHK/unarchive").data["is_archived"] is False
    assert as_user("yanis").post("/api/v1/projects/CHK/archive").status_code == 403


def test_pm_updates_project_lead(as_user):
    sara = User.objects.get(email="sara@digitalia.io")
    r = as_user("yanis").patch("/api/v1/projects/SCV", {"lead": sara.id, "description": "Nouveau texte"}, format="json")
    assert r.status_code == 200 and r.data["lead"]["id"] == sara.id
    assert as_user("sara").patch("/api/v1/projects/SCV", {"name": "x"}, format="json").status_code == 403


def test_organizations_listing(as_user):
    data = as_user("admin").get("/api/v1/organizations").data
    wws = next(o for o in data if o["name"] == "WWS")
    assert [p["key"] for p in wws["projects"]] == ["CHK", "SCV"]
    assert wws["users"][0]["email"] == "julie@wws.fr" and wws["users"][0]["projects"] == ["CHK", "SCV"]


# ---------- Critère d'acceptation Sprint 4 ----------

def test_sprint4_acceptance_scenario(as_user, mailoutbox, django_capture_on_commit_callbacks):
    admin = as_user("admin")
    with django_capture_on_commit_callbacks(execute=True):
        r = admin.post("/api/v1/organizations", {"name": "Atlas Énergie", "contact_name": "Karim Haddad",
                                                 "contact_email": "karim@atlas-energie.fr"}, format="json")
    assert r.status_code == 201
    org = Organization.objects.get(name="Atlas Énergie")
    lead = User.objects.get(email="sara@digitalia.io")
    r = admin.post("/api/v1/projects", {"key": "ATL", "name": "Portail Atlas", "client": org.id, "lead": lead.id,
                                        "dev_price": "20000", "licence_amount": "700"}, format="json")
    assert r.status_code == 201

    invite = next(m for m in mailoutbox if m.to == ["karim@atlas-energie.fr"])
    r = APIClient().post("/api/v1/auth/invite/accept", {**link_params(invite.body), "password": "Atlas-2026!"},
                         format="json")
    assert r.status_code == 200
    r = login("karim@atlas-energie.fr", "Atlas-2026!")
    assert r.status_code == 200
    assert [p["key"] for p in r.data["me"]["projects"]] == ["ATL"]
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION="Bearer " + r.data["access"])
    r = client.post("/api/v1/tickets", {"project": "ATL", "type": "question", "title": "Accès pour mon équipe ?"},
                    format="multipart")
    assert r.status_code == 201 and r.data["ref"] == "ATL-1"
    assert client.get("/api/v1/tickets?project=SCV").data["results"] == []  # règle 1
