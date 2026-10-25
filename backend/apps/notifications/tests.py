"""Règles 24 à 26 (notifications) : destinataires, réglages, rappel, digest, e-mails."""
from datetime import timedelta

import pytest
from django.utils import timezone

from apps.accounts.models import Organization, User
from apps.notifications.models import Notification, NotificationSetting
from apps.notifications.tasks import daily_digest, remind_waiting_clients
from apps.projects.models import Project, ProjectAccess
from apps.tickets.models import Ticket, TicketEvent


def ticket(ref):
    key, num = ref.split("-")
    return Ticket.objects.get(project__key=key, number=int(num))


def kinds_for(email):
    return list(Notification.objects.filter(user__email=email).values_list("kind", flat=True))


def move(client, t, to, **extra):
    r = client.post(f"/api/v1/tickets/{t.id}/transition", {"to": to, **extra}, format="json")
    assert r.status_code == 200, r.data
    return r


@pytest.fixture
def mails(mailoutbox, monkeypatch):
    """Envois « après commit » exécutés immédiatement (la transaction de test n'est jamais validée)."""
    from django.db import transaction

    monkeypatch.setattr(transaction, "on_commit", lambda func, using=None, robust=False: func())
    return mailoutbox


# ---------- Règle 24 : côté client ----------

def test_client_is_told_when_planned_with_date(as_user, mails):
    t = ticket("CHK-2")  # nouveau, évolution incluse licence
    t.due_on = timezone.localdate() + timedelta(days=10)
    t.save()
    move(as_user("yanis"), t, "faire")
    assert kinds_for("julie@wws.fr") == ["planned"]
    mail = next(m for m in mails if m.to == ["julie@wws.fr"])
    assert "CHK-2 est planifiée" in mail.subject and "Livraison prévue le" in mail.body


@pytest.mark.parametrize("ref,to,kind", [("SCV-2", "attente", "info_requested"), ("CHK-4", "test", "ready_to_test"),
                                         ("RMC-9", "analyser", "qualified")])
def test_client_status_notifications(as_user, mails, ref, to, kind):
    move(as_user("sara"), ticket(ref), to)
    client_email = {"SCV": "julie@wws.fr", "CHK": "julie@wws.fr", "RMC": "marc@rmclub.fr"}[ref.split("-")[0]]
    assert kinds_for(client_email) == [kind]
    assert any(m.to == [client_email] for m in mails)


def test_quote_sent_notifies_client(as_user, mails):
    t = ticket("RMC-9")
    as_user("yanis").post(f"/api/v1/tickets/{t.id}/triage", {"decision": "devis", "quote": {"amount_ht": "900"}},
                          format="json")
    assert kinds_for("marc@rmclub.fr") == ["quote_sent"]  # pas de « qualifiée » en double


def test_delivered_notifies_other_client_users_not_the_actor(as_user, mails):
    wws = Organization.objects.get(name="WWS")
    paul = User.objects.create_user("paul@wws.fr", "orbit-pass-1", organization=wws, job="client", first_name="Paul")
    ProjectAccess.objects.create(user=paul, project=Project.objects.get(key="SCV"))
    move(as_user("julie"), ticket("SCV-10"), "termine")
    assert kinds_for("paul@wws.fr") == ["delivered"] and kinds_for("julie@wws.fr") == []


# ---------- Règle 25 : côté Digitalia ----------

def test_new_client_request_notifies_lead_and_pms(as_user, mails):
    as_user("julie").post("/api/v1/tickets", {"project": "CHK", "type": "bug", "title": "Crash"}, format="multipart")
    notified = set(Notification.objects.filter(kind="new_request").values_list("user__email", flat=True))
    assert notified == {"sara@digitalia.io", "yanis@digitalia.io", "admin@digitalia.io"}  # lead CHK = Sara + pm/admin


def test_digitalia_ticket_does_not_notify_new_request(as_user, mails):
    as_user("yanis").post("/api/v1/tickets", {"project": "CHK", "type": "bug", "title": "Crash"}, format="multipart")
    assert not Notification.objects.filter(kind="new_request").exists()


def test_client_reply_and_test_notify_team(as_user, mails):
    julie = as_user("julie")
    julie.post(f"/api/v1/tickets/{ticket('SCV-7').id}/comments", {"body": "Voici le logo en SVG."}, format="multipart")
    assert set(Notification.objects.filter(kind="client_replied").values_list("user__email", flat=True)) == {
        "yanis@digitalia.io"}  # responsable SCV + assigné (Yanis)
    move(julie, ticket("SCV-10"), "cours", comment="Le filtre ignore la date de fin.")
    n = Notification.objects.get(kind="client_tested", user__email="sara@digitalia.io")
    assert n.payload == {"ok": False}


def test_quote_decision_notifies_team(as_user, mails):
    as_user("julie").post(f"/api/v1/tickets/{ticket('SCV-3').id}/quote/accept")
    notified = set(Notification.objects.filter(kind="quote_decided").values_list("user__email", flat=True))
    assert notified == {"yanis@digitalia.io", "admin@digitalia.io"}


def test_daily_digest(as_user, mails):
    as_user("julie").post("/api/v1/tickets", {"project": "SCV", "type": "bug", "title": "Crash"}, format="multipart")
    Notification.objects.all().delete()
    assert daily_digest() == 2  # Yanis (pm) + Yasmina (admin)
    assert any("nouvelle(s) demande(s)" in m.subject and "Crash" in m.body for m in mails)


# ---------- Règle 26 : rien sur un ticket interne ----------

def test_no_notification_on_internal_ticket(as_user, mails):
    move(as_user("sara"), ticket("SCV-4"), "cours")  # sous-tâche interne
    assert not Notification.objects.exists() and not mails


# ---------- Réglages, rappel, relance ----------

def test_settings_disable_a_notification(as_user, mails):
    r = as_user("yanis").put("/api/v1/settings/notifications", {"client_info_requested": False}, format="json")
    assert r.status_code == 200 and r.data["client_info_requested"] is False
    move(as_user("sara"), ticket("SCV-2"), "attente")
    assert kinds_for("julie@wws.fr") == []


def test_reminder_after_n_days_once(as_user, mails):
    s = NotificationSetting.load()
    s.client_reminder, s.reminder_days = True, 3
    s.save()
    t = ticket("SCV-10")  # en test client
    TicketEvent.objects.create(ticket=t, kind="status", to_value="test", at=timezone.now() - timedelta(days=4))
    TicketEvent.objects.filter(ticket=t, kind="status").exclude(at__lt=timezone.now() - timedelta(days=3)).delete()
    Ticket.objects.filter(pk=t.pk).update(created_at=timezone.now() - timedelta(days=10))
    assert remind_waiting_clients() >= 1
    assert kinds_for("julie@wws.fr").count("reminder") >= 1
    before = Notification.objects.filter(kind="reminder").count()
    remind_waiting_clients()
    assert Notification.objects.filter(kind="reminder").count() == before  # pas de doublon


def test_reminder_disabled_by_default(seeded):
    assert remind_waiting_clients() == 0


def test_manual_ping_always_notifies(as_user, mails):
    as_user("yanis").post(f"/api/v1/tickets/{ticket('SCV-7').id}/ping")
    assert kinds_for("julie@wws.fr") == ["reminder"]


def test_notifications_endpoint(as_user, mails):
    move(as_user("sara"), ticket("SCV-2"), "attente")
    julie = as_user("julie")
    data = julie.get("/api/v1/notifications").data
    assert data["unread"] == 1 and data["results"][0]["title"].startswith("Digitalia a besoin")
    nid = data["results"][0]["id"]
    assert julie.post(f"/api/v1/notifications/{nid}/read").data["unread"] == 0
    assert as_user("marc").post(f"/api/v1/notifications/{nid}/read").status_code == 404
