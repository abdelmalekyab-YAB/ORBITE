"""Workflow configurable (docs/03-workflow.md, « Configurabilité »)."""
import pytest

from apps.projects.models import WorkflowStatus
from apps.tickets.models import Ticket


def current(client, qs=""):
    return client.get(f"/api/v1/workflow{qs}").data


def spec(data):
    return [{k: s[k] for k in ("key", "label", "client_label", "ball", "is_closed", "is_terminal_ok", "color", "next")}
            for s in data["statuses"]]


@pytest.mark.parametrize("login,code", [("sara", 403), ("julie", 403)])
def test_only_pm_admin_can_edit(as_user, login, code):
    c = as_user(login)
    assert c.put("/api/v1/workflow", {"statuses": spec(current(c))}, format="json").status_code == code
    assert c.post("/api/v1/workflow/reset").status_code == code


def test_rename_client_label_updates_track(as_user):
    yanis = as_user("yanis")
    s = spec(current(yanis))
    next(x for x in s if x["key"] == "testint")["client_label"] = "Recette interne"
    r = yanis.put("/api/v1/workflow", {"statuses": s}, format="json")
    assert r.status_code == 200 and "Recette interne" in r.data["steps"]
    assert as_user("julie").get(f"/api/v1/tickets/{Ticket.objects.get(project__key='CHK', number=4).id}").data[
        "client_label"] == "Recette interne"


def test_add_status_with_transitions(as_user):
    yanis = as_user("yanis")
    s = spec(current(yanis))
    s.insert(5, {"key": "revue", "label": "Revue de code", "client_label": "Validation interne", "ball": "digitalia",
                 "next": ["testint", "cours"]})
    next(x for x in s if x["key"] == "cours")["next"].append("revue")
    r = yanis.put("/api/v1/workflow", {"statuses": s}, format="json")
    assert r.status_code == 200
    t = Ticket.objects.get(project__key="SCV", number=2)  # en cours
    assert yanis.post(f"/api/v1/tickets/{t.id}/transition", {"to": "revue"}, format="json").status_code == 200
    board = as_user("sara").get("/api/v1/tickets/board?project=SCV").data["columns"]
    assert "revue" in [c["key"] for c in board]


def test_cannot_delete_used_or_system_status(as_user):
    yanis = as_user("yanis")
    s = [x for x in spec(current(yanis)) if x["key"] != "attente"]
    for x in s:
        x["next"] = [n for n in x["next"] if n != "attente"]
    r = yanis.put("/api/v1/workflow", {"statuses": s}, format="json")
    used = Ticket.objects.filter(status__key="attente").count()
    assert r.status_code == 409 and f"utilisé par {used} ticket" in r.data["detail"]
    s = [x for x in spec(current(yanis)) if x["key"] != "annule"]
    r = yanis.put("/api/v1/workflow", {"statuses": s}, format="json")
    assert r.status_code == 409


def test_delete_unused_status_and_reset(as_user):
    yanis = as_user("yanis")
    s = [x for x in spec(current(yanis)) if x["key"] != "analyser"]
    for x in s:
        x["next"] = [n for n in x["next"] if n != "analyser"]
    Ticket.objects.filter(status__key="analyser").delete()
    assert yanis.put("/api/v1/workflow", {"statuses": s}, format="json").status_code == 200
    assert not WorkflowStatus.objects.filter(key="analyser", project__isnull=True).exists()
    r = yanis.post("/api/v1/workflow/reset")
    assert r.status_code == 200 and [x["key"] for x in r.data["statuses"]][:3] == ["nouveau", "analyser", "devis"]


def test_invalid_transition_target_rejected(as_user):
    yanis = as_user("yanis")
    s = spec(current(yanis))
    s[0]["next"].append("inexistant")
    assert yanis.put("/api/v1/workflow", {"statuses": s}, format="json").status_code == 400


def test_project_customization_copies_and_remaps(as_user):
    yanis = as_user("yanis")
    s = spec(current(yanis, "?project=SCV"))
    next(x for x in s if x["key"] == "test")["client_label"] = "Recette"
    r = yanis.put("/api/v1/workflow?project=SCV", {"statuses": s}, format="json")
    assert r.status_code == 200 and r.data["customized"] is True and "Recette" in r.data["steps"]
    t = Ticket.objects.get(project__key="SCV", number=10)
    assert t.status.project.key == "SCV" and t.status.key == "test"
    assert "Recette" not in current(yanis)["steps"]  # global inchangé
    other = Ticket.objects.get(project__key="CHK", number=4)
    assert other.status.project is None
    r = yanis.post("/api/v1/workflow/reset?project=SCV")
    assert r.status_code == 200 and r.data["customized"] is False
    t.refresh_from_db()
    assert t.status.project is None and t.status.key == "test"
