"""Règles métier 1, 2, 6 à 12 (docs/04-regles-metier.md) et scénario d'acceptation du Sprint 1."""
from datetime import timedelta

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone

from apps.projects.models import Project
from apps.tickets.models import Comment, Ticket, TicketEvent


def ticket(ref: str) -> Ticket:
    key, num = ref.split("-")
    return Ticket.objects.get(project__key=key, number=int(num))


def voice_note():
    return SimpleUploadedFile("vocal.webm", b"\x1a\x45\xdf\xa3fake", content_type="audio/webm")


def new_bug(client, project="SCV", **extra):
    data = {"project": project, "type": "bug", "title": "Le bouton Enregistrer ne répond plus",
            "description": "Rien ne se passe au clic.", "impact": "bloquant", **extra}
    return client.post("/api/v1/tickets", data, format="multipart")


# ---------- Règles 1-2 : visibilité, appliquée dans les querysets ----------

def test_client_only_sees_own_projects_and_no_internal(as_user):
    julie = as_user("julie")
    refs = {t["ref"] for t in julie.get("/api/v1/tickets").data["results"]}
    assert refs and all(r.split("-")[0] in {"SCV", "CHK"} for r in refs)
    assert "SCV-4" not in refs and "SCV-8" not in refs  # tâches internes
    assert julie.get(f"/api/v1/tickets/{ticket('SCV-4').id}").status_code == 404
    assert julie.get(f"/api/v1/tickets/{ticket('RMC-2').id}").status_code == 404  # autre organisation


def test_client_payload_hides_internal_fields(as_user):
    data = as_user("julie").get(f"/api/v1/tickets/{ticket('SCV-3').id}").data
    assert "is_internal" not in data and "estimate_days" not in data and data["children"] == []
    assert len(as_user("yanis").get(f"/api/v1/tickets/{ticket('SCV-3').id}").data["children"]) == 3


def test_client_without_access_sees_empty_list(as_user):
    from apps.projects.models import ProjectAccess

    ProjectAccess.objects.filter(user__email="marc@rmclub.fr").delete()
    marc = as_user("marc")
    assert marc.get("/api/v1/projects").data == []
    assert marc.get("/api/v1/tickets").data["results"] == []


def test_client_cannot_access_digitalia_endpoints(as_user):
    julie = as_user("julie")
    assert julie.get("/api/v1/tickets/board").status_code == 403
    assert julie.get("/api/v1/cockpit").status_code == 403
    assert julie.get("/api/v1/team").status_code == 403


# ---------- Règle 6 : numérotation ----------

def test_numbering_is_sequential_and_never_reused(as_user):
    julie = as_user("julie")
    first = new_bug(julie).data
    assert first["ref"] == "SCV-11"
    Ticket.objects.filter(pk=first["id"]).delete()
    assert new_bug(julie).data["ref"] == "SCV-12"
    assert new_bug(julie, project="CHK").data["ref"] == "CHK-5"


# ---------- Règle 7 : création par un client ----------

def test_client_creation_defaults_and_attachments(as_user):
    photo = SimpleUploadedFile("ecran.png", b"\x89PNG", content_type="image/png")
    r = new_bug(as_user("julie"), attachments=[photo, voice_note()])
    assert r.status_code == 201, r.data
    t = ticket(r.data["ref"])
    assert (t.origin, t.status.key, t.is_internal, t.priority) == ("client", "nouveau", False, "critical")
    assert {a["content_type"] for a in r.data["attachments"]} == {"image/png", "audio/webm"}
    assert TicketEvent.objects.filter(ticket=t, kind="created").exists()


@pytest.mark.parametrize("impact,priority", [("confort", "normal"), ("genant", "high"), ("bloquant", "critical")])
def test_client_impact_maps_to_priority(as_user, impact, priority):
    assert new_bug(as_user("julie"), impact=impact).data["priority"] == priority


def test_client_cannot_create_internal_or_forge_fields(as_user):
    julie = as_user("julie")
    assert new_bug(julie, type="internal").status_code == 400
    r = new_bug(julie, is_internal=True, initial_status="faire")
    t = ticket(r.data["ref"])
    assert t.is_internal is False and t.status.key == "nouveau"
    assert new_bug(julie, project="RMC").status_code == 403


# ---------- Règle 8 : création par Digitalia ----------

def test_digitalia_creation(as_user):
    yanis = as_user("yanis")
    r = new_bug(yanis)
    assert ticket(r.data["ref"]).status.key == "faire" and r.data["origin"] == "digitalia"
    assert ticket(new_bug(yanis, initial_status="nouveau").data["ref"]).status.key == "nouveau"
    t = ticket(new_bug(yanis, type="internal", parent=ticket("SCV-3").id).data["ref"])
    assert t.is_internal and t.parent.number == 3


# ---------- Règle 9 : toute transition passe par le service ----------

def test_transition_not_allowed_returns_409(as_user):
    t = ticket("SCV-9")  # faire
    r = as_user("yanis").post(f"/api/v1/tickets/{t.id}/transition", {"to": "termine"}, format="json")
    assert r.status_code == 409 and r.data["code"] == "transition_not_allowed"
    t.refresh_from_db()
    assert t.status.key == "faire"


def test_transition_writes_history_and_closed_at(as_user):
    t = ticket("SCV-10")  # test client
    r = as_user("julie").post(f"/api/v1/tickets/{t.id}/transition", {"to": "termine"}, format="json")
    assert r.status_code == 200
    t.refresh_from_db()
    assert t.status.key == "termine" and t.closed_at is not None
    assert TicketEvent.objects.filter(ticket=t, kind="status", from_value="test", to_value="termine").exists()


def test_client_cannot_use_digitalia_transitions(as_user):
    t = ticket("SCV-2")  # cours → testint est une action Digitalia
    r = as_user("julie").post(f"/api/v1/tickets/{t.id}/transition", {"to": "testint"}, format="json")
    assert r.status_code == 403


def test_patch_is_digitalia_only_and_logged(as_user):
    t = ticket("SCV-2")
    assert as_user("julie").patch(f"/api/v1/tickets/{t.id}", {"title": "x"}, format="json").status_code == 403
    yanis = as_user("yanis")
    r = yanis.patch(f"/api/v1/tickets/{t.id}", {"assignee": yanis.user.id, "status": "termine"}, format="json")
    assert r.status_code == 200 and r.data["assignee"]["id"] == yanis.user.id
    t.refresh_from_db()
    assert t.status.key == "cours"  # le statut ne se modifie pas par PATCH
    assert TicketEvent.objects.filter(ticket=t, kind="assignee").exists()


# ---------- Règle 10 : refus obligatoire ----------

def test_refusal_without_reason_is_rejected(as_user):
    t = ticket("SCV-10")
    r = as_user("julie").post(f"/api/v1/tickets/{t.id}/transition", {"to": "cours", "comment": "non"},
                              format="multipart")
    assert r.status_code == 400 and r.data["code"] == "reason_required"
    t.refresh_from_db()
    assert t.status.key == "test"


def test_refusal_with_text_reason(as_user):
    t = ticket("SCV-10")
    r = as_user("julie").post(f"/api/v1/tickets/{t.id}/transition",
                              {"to": "cours", "comment": "Le filtre ignore la date de fin."}, format="multipart")
    assert r.status_code == 200
    assert Comment.objects.get(ticket=t, kind="refusal").body.startswith("Le filtre")


def test_refusal_with_voice_note_only(as_user):
    t = ticket("SCV-10")
    r = as_user("julie").post(f"/api/v1/tickets/{t.id}/transition", {"to": "cours", "attachments": [voice_note()]},
                              format="multipart")
    assert r.status_code == 200
    refusal = next(c for c in r.data["comments"] if c["kind"] == "refusal")
    assert refusal["attachments"][0]["content_type"] == "audio/webm"


def test_image_alone_is_not_a_valid_reason(as_user):
    t = ticket("SCV-10")
    img = SimpleUploadedFile("a.png", b"\x89PNG", content_type="image/png")
    r = as_user("julie").post(f"/api/v1/tickets/{t.id}/transition", {"to": "cours", "attachments": [img]},
                              format="multipart")
    assert r.status_code == 400


def test_reopen_requires_reason(as_user):
    t = ticket("SCV-1")  # termine
    julie = as_user("julie")
    assert julie.post(f"/api/v1/tickets/{t.id}/transition", {"to": "cours"}, format="json").status_code == 400
    r = julie.post(f"/api/v1/tickets/{t.id}/transition", {"to": "cours", "comment": "L'export est de nouveau vide."},
                   format="json")
    assert r.status_code == 200 and Comment.objects.filter(ticket=t, kind="reopen").exists()


def test_digitalia_can_take_back_a_test_without_reason(as_user):
    t = ticket("SCV-10")  # test client → « Reprendre »
    assert as_user("sara").post(f"/api/v1/tickets/{t.id}/transition", {"to": "cours"}, format="json").status_code == 200


# ---------- Règle 11 : le client répond → la balle revient chez Digitalia ----------

def test_client_comment_on_waiting_ticket_moves_to_cours(as_user):
    t = ticket("SCV-7")  # attente
    r = as_user("julie").post(f"/api/v1/tickets/{t.id}/comments", {"body": "Voici le logo en SVG."},
                              format="multipart")
    assert r.status_code == 201 and r.data["status"] == "cours" and r.data["ball"] == "digitalia"


def test_digitalia_comment_does_not_move_waiting_ticket(as_user):
    t = ticket("SCV-7")
    as_user("yanis").post(f"/api/v1/tickets/{t.id}/comments", {"body": "Toujours besoin du logo."})
    t.refresh_from_db()
    assert t.status.key == "attente"


def test_empty_comment_rejected(as_user):
    assert as_user("julie").post(f"/api/v1/tickets/{ticket('SCV-7').id}/comments", {"body": " "}).status_code == 400


# ---------- Règle 12 : retard calculé ----------

def test_late_is_computed(as_user):
    t = ticket("SCV-2")
    t.due_on = timezone.localdate() - timedelta(days=1)
    t.save()
    closed = ticket("SCV-1")
    closed.due_on = timezone.localdate() - timedelta(days=10)
    closed.save()
    yanis = as_user("yanis")
    late = {x["ref"] for x in yanis.get("/api/v1/tickets?late=1&project=SCV").data["results"]}
    assert "SCV-2" in late and "SCV-1" not in late
    assert yanis.get(f"/api/v1/tickets/{t.id}").data["is_late"] is True


# ---------- Board, cockpit, filtres ----------

def test_board_columns_come_from_workflow(as_user):
    cols = as_user("sara").get("/api/v1/tickets/board?project=SCV").data["columns"]
    keys = [c["key"] for c in cols]
    assert keys == ["nouveau", "analyser", "client", "faire", "cours", "testint", "termine"]
    client_col = next(c for c in cols if c["key"] == "client")
    assert set(client_col["statuses"]) == {"devis", "attente", "test"}
    assert {c["ref"] for c in client_col["cards"]} == {"SCV-3", "SCV-7", "SCV-10"}


def test_ball_filter_and_cockpit(as_user):
    julie = as_user("julie")
    mine = {t["ref"] for t in julie.get("/api/v1/tickets?ball=client").data["results"]}
    assert mine == {"SCV-3", "SCV-7", "SCV-10"}
    cockpit = as_user("admin").get("/api/v1/cockpit").data
    assert {p["key"] for p in cockpit["projects"]} == {"SCV", "CHK", "RMC", "TWM"}
    assert next(b for b in cockpit["to_handle"] if b["key"] == "testint")["tickets"][0]["ref"] == "CHK-4"


def test_client_activity_feed_excludes_internal_and_other_orgs(as_user):
    refs = {e["ticket"]["ref"] for e in as_user("julie").get("/api/v1/activity").data}
    assert refs and all(r.split("-")[0] in {"SCV", "CHK"} for r in refs)
    internal = {t.ref for t in Ticket.objects.filter(is_internal=True, project__key__in=["SCV", "CHK"])}
    assert not refs & internal


def test_workflow_endpoint_exposes_steps(as_user):
    data = as_user("julie").get("/api/v1/workflow").data
    assert data["steps"] == ["Reçue", "Proposition à valider", "Planifiée", "En développement",
                             "Validation interne", "À tester", "Livrée"]


# ---------- Scénario d'acceptation Sprint 1 ----------

def test_sprint1_acceptance_scenario(as_user):
    """Bug de Julie : cours → testint → test → « Pas OK » avec vocal → cours → test → livré."""
    julie, sara, yanis = as_user("julie"), as_user("sara"), as_user("yanis")
    tid = new_bug(julie).data["id"]
    url = f"/api/v1/tickets/{tid}/transition"

    def move(who, to, **extra):
        r = who.post(url, {"to": to, **extra}, format="multipart")
        assert r.status_code == 200, (to, r.data)
        return r.data

    move(yanis, "faire")
    move(sara, "cours")
    move(sara, "testint")
    assert move(sara, "test")["ball"] == "client"
    refused = move(julie, "cours", attachments=[voice_note()])
    assert refused["ball"] == "digitalia"
    assert any(c["kind"] == "refusal" and c["attachments"] for c in refused["comments"])
    move(sara, "testint")
    move(sara, "test")
    done = move(julie, "termine")
    assert done["client_label"] == "Livrée" and done["is_closed"]

    history = [(e["from_value"], e["to_value"]) for e in julie.get(f"/api/v1/tickets/{tid}/events").data
               if e["kind"] == "status"]
    assert history == [("nouveau", "faire"), ("faire", "cours"), ("cours", "testint"), ("testint", "test"),
                       ("test", "cours"), ("cours", "testint"), ("testint", "test"), ("test", "termine")]


def test_test_dataset_is_idempotent(seeded):
    from tests_support.demo_data import load_demo

    load_demo()
    assert Project.objects.get(key="SCV").tickets.count() == 10
    assert Ticket.objects.count() == 34
