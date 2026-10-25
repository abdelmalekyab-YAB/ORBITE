"""Règles 13 à 18 (triage et devis) et scénario d'acceptation du Sprint 2."""
from datetime import timedelta
from decimal import Decimal

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone

from apps.projects.models import Milestone
from apps.tickets.models import Comment, Quote, Ticket, TicketEvent
from apps.tickets.quotes import split_amount


def ticket(ref: str) -> Ticket:
    key, num = ref.split("-")
    return Ticket.objects.get(project__key=key, number=int(num))


def new_evolution(as_user, project="SCV") -> Ticket:
    r = as_user("julie").post("/api/v1/tickets", {"project": project, "type": "evolution", "title": "Export Excel",
                                                  "description": "Exporter la liste en Excel.", "impact": "confort"},
                              format="multipart")
    return ticket(r.data["ref"])


def triage(client, t: Ticket, **data):
    return client.post(f"/api/v1/tickets/{t.id}/triage", data, format="json")


QUOTE = {"amount_ht": "1800.00", "parts": 2, "description": "Export Excel des résultats, livré en 2.4."}


# ---------- Règle 13 : file de triage et décisions ----------

def test_triage_queue_lists_new_and_analysing_only(as_user):
    refs = [t["ref"] for t in as_user("yanis").get("/api/v1/triage").data]
    statuses = {ticket(r).status.key for r in refs}
    assert refs and statuses <= {"nouveau", "analyser"}
    assert "CHK-2" in refs and "RMC-9" in refs


@pytest.mark.parametrize("login", ["sara", "julie"])
def test_triage_is_pm_admin_only(as_user, login):
    client = as_user(login)
    assert client.get("/api/v1/triage").status_code == 403
    assert triage(client, ticket("CHK-2"), decision="analyser").status_code == 403


def test_triage_plan_with_fields_and_message(as_user):
    yanis, sara = as_user("yanis"), as_user("sara")
    t = ticket("CHK-2")  # évolution, facturation licence
    ms = Milestone.objects.get(project__key="CHK", name="Version 2.4")
    r = triage(yanis, t, decision="faire", assignee=sara.user.id, milestone=ms.id, due_on="2026-10-10",
               estimate_days="1.5", priority="high", message="Merci, c'est planifié dans la version 2.4.")
    assert r.status_code == 200, r.data
    t.refresh_from_db()
    assert (t.status.key, t.assignee, t.milestone, str(t.due_on), t.estimate_days, t.priority) == (
        "faire", sara.user, ms, "2026-10-10", Decimal("1.5"), "high")
    assert Comment.objects.filter(ticket=t, body__startswith="Merci, c'est planifié").exists()
    assert TicketEvent.objects.filter(ticket=t, kind="assignee").exists()
    assert TicketEvent.objects.filter(ticket=t, kind="status", from_value="nouveau", to_value="faire").exists()


@pytest.mark.parametrize("decision,status", [("analyser", "analyser"), ("attente", "attente"), ("refuse", "refuse")])
def test_triage_other_decisions(as_user, decision, status):
    t = ticket("RMC-9")
    r = triage(as_user("admin"), t, decision=decision, message="Pouvez-vous préciser la période ?")
    assert r.status_code == 200
    t.refresh_from_db()
    assert t.status.key == status


def test_triage_refused_once_ticket_is_planned(as_user):
    assert triage(as_user("yanis"), ticket("SCV-9"), decision="analyser").status_code == 409  # déjà « À faire »


# ---------- Règle 14 : facturation avant planification ----------

def test_evolution_needs_billing_before_planning(as_user):
    t = new_evolution(as_user)
    r = triage(as_user("yanis"), t, decision="faire")
    assert r.status_code == 400 and r.data["code"] == "billing_required"
    assert triage(as_user("yanis"), t, decision="faire", billing="licence").status_code == 200


def test_quote_billing_cannot_be_planned_without_accepted_quote(as_user):
    t = new_evolution(as_user)
    r = triage(as_user("yanis"), t, decision="faire", billing="quote")
    assert r.status_code == 400 and r.data["code"] == "quote_required"
    t.refresh_from_db()
    assert t.status.key == "nouveau"  # rien n'a été appliqué


def test_rule14_also_applies_to_direct_transitions(as_user):
    """Bouton « Planifier » ou glisser-déposer kanban : même contrôle que le triage."""
    t = new_evolution(as_user)
    r = as_user("yanis").post(f"/api/v1/tickets/{t.id}/transition", {"to": "faire"}, format="json")
    assert r.status_code == 400 and r.data["code"] == "billing_required"
    Ticket.objects.filter(pk=t.pk).update(billing="quote")
    r = as_user("yanis").post(f"/api/v1/tickets/{t.id}/transition", {"to": "faire"}, format="json")
    assert r.status_code == 400 and r.data["code"] == "quote_required"


def test_bug_can_be_planned_without_billing(as_user):
    r = as_user("julie").post("/api/v1/tickets", {"project": "SCV", "type": "bug", "title": "Crash à l'export"},
                              format="multipart")
    assert triage(as_user("yanis"), ticket(r.data["ref"]), decision="faire").status_code == 200


@pytest.mark.parametrize("amount", ["0", "-10"])
def test_quote_requires_positive_amount(as_user, amount):
    t = new_evolution(as_user)
    r = triage(as_user("yanis"), t, decision="devis", quote={**QUOTE, "amount_ht": amount})
    assert r.status_code == 400 and r.data["code"] == "invalid_amount"
    assert not Quote.objects.filter(ticket=t).exists()


# ---------- Règle 15 : envoi ----------

def test_send_quote(as_user):
    t = new_evolution(as_user)
    r = triage(as_user("yanis"), t, decision="devis", quote=QUOTE)
    assert r.status_code == 200, r.data
    assert r.data["status"] == "devis" and r.data["ball"] == "client" and r.data["billing"] == "quote"
    q = Quote.objects.get(ticket=t)
    assert (q.status, q.amount_ht, q.parts) == ("sent", Decimal("1800.00"), 2) and q.sent_at
    assert TicketEvent.objects.filter(ticket=t, kind="quote_sent").exists()
    detail = as_user("julie").get(f"/api/v1/tickets/{t.id}").data
    assert detail["quote_detail"]["amount_ht"] == "1800.00" and detail["quote"]["status"] == "sent"


def test_send_quote_with_pdf_in_multipart(as_user):
    t = new_evolution(as_user)
    pdf = SimpleUploadedFile("devis.pdf", b"%PDF-1.4 test", content_type="application/pdf")
    r = as_user("yanis").post(f"/api/v1/tickets/{t.id}/triage",
                              {"decision": "devis", "quote_amount_ht": "900", "quote_parts": 1, "quote_pdf": pdf},
                              format="multipart")
    assert r.status_code == 200, r.data
    assert r.data["quote_detail"]["pdf"].endswith(".pdf")


# ---------- Règle 16 : acceptation ----------

@pytest.mark.parametrize("amount,parts,expected", [
    ("3600", 1, ["3600.00"]), ("3600", 2, ["1800.00", "1800.00"]), ("1000", 3, ["300.00", "400.00", "300.00"]),
    ("100.01", 3, ["30.00", "40.00", "30.01"]),
])
def test_split_amount(amount, parts, expected):
    assert [str(x) for x in split_amount(Decimal(amount), parts)] == expected


def test_client_accepts_quote(as_user):
    t = ticket("SCV-3")  # devis envoyé par le seed, 3 600 € en 2 parts
    r = as_user("julie").post(f"/api/v1/tickets/{t.id}/quote/accept")
    assert r.status_code == 200, r.data
    assert r.data["status"] == "faire"
    q = Quote.objects.get(ticket=t)
    today = timezone.localdate()
    assert q.status == "accepted" and q.decided_by.email == "julie@wws.fr" and q.decided_at
    assert [(i.due_on, i.amount) for i in q.installments.all()] == [
        (today, Decimal("1800.00")), (today + timedelta(days=45), Decimal("1800.00"))]
    assert TicketEvent.objects.filter(ticket=t, kind="quote_accepted").exists()


def test_only_clients_with_access_can_decide(as_user):
    t = ticket("SCV-3")
    assert as_user("admin").post(f"/api/v1/tickets/{t.id}/quote/accept").status_code == 403
    assert as_user("marc").post(f"/api/v1/tickets/{t.id}/quote/accept").status_code == 404
    assert as_user("marc").get(f"/api/v1/tickets/{t.id}/quote").status_code == 404


def test_cannot_accept_twice(as_user):
    t = ticket("SCV-3")
    julie = as_user("julie")
    julie.post(f"/api/v1/tickets/{t.id}/quote/accept")
    r = julie.post(f"/api/v1/tickets/{t.id}/quote/accept")
    assert r.status_code == 400 and r.data["code"] == "no_pending_quote"


# ---------- Règle 17 : refus motivé ----------

def test_refuse_quote_requires_reason(as_user):
    t = ticket("SCV-3")
    julie = as_user("julie")
    r = julie.post(f"/api/v1/tickets/{t.id}/quote/refuse", {"reason": "cher"}, format="multipart")
    assert r.status_code == 400 and r.data["code"] == "reason_required"
    assert Quote.objects.get(ticket=t).status == "sent"
    r = julie.post(f"/api/v1/tickets/{t.id}/quote/refuse", {"reason": "Budget déjà engagé cette année."},
                   format="multipart")
    assert r.status_code == 200 and r.data["status"] == "refuse"
    assert Quote.objects.get(ticket=t).status == "refused"
    assert Comment.objects.filter(ticket=t, kind="quote_refusal", body__startswith="Budget").exists()
    assert TicketEvent.objects.filter(ticket=t, kind="quote_refused").exists()


def test_refuse_quote_with_voice_note(as_user):
    t = ticket("SCV-3")
    voice = SimpleUploadedFile("vocal.webm", b"x", content_type="audio/webm")
    r = as_user("julie").post(f"/api/v1/tickets/{t.id}/quote/refuse", {"attachments": [voice]}, format="multipart")
    assert r.status_code == 200


# ---------- Règle 18 : modification et renvoi ----------

def test_modify_then_resend_quote(as_user):
    t = ticket("SCV-3")
    yanis, julie = as_user("yanis"), as_user("julie")
    r = yanis.patch(f"/api/v1/tickets/{t.id}/quote", {"amount_ht": "3200.00"}, format="json")
    assert r.status_code == 200 and r.data["status"] == "draft"
    assert julie.post(f"/api/v1/tickets/{t.id}/quote/accept").status_code == 400  # en cours de modification
    assert julie.get(f"/api/v1/tickets/{t.id}").data["quote_detail"]["status"] == "draft"
    r = yanis.post(f"/api/v1/tickets/{t.id}/quote/send")
    assert r.status_code == 200 and r.data["quote_detail"]["status"] == "sent"
    assert r.data["quote_detail"]["amount_ht"] == "3200.00"
    assert TicketEvent.objects.filter(ticket=t, kind="quote_updated").exists()


def test_client_cannot_modify_quote_nor_see_unsent_draft(as_user):
    t = ticket("SCV-3")
    assert as_user("julie").patch(f"/api/v1/tickets/{t.id}/quote", {"amount_ht": "1"}, format="json").status_code == 403
    fresh = new_evolution(as_user)
    Quote.objects.create(ticket=fresh, amount_ht=Decimal("500"))  # brouillon jamais envoyé
    assert as_user("julie").get(f"/api/v1/tickets/{fresh.id}").data["quote_detail"] is None
    assert as_user("julie").get(f"/api/v1/tickets/{fresh.id}/quote").status_code == 404


def test_cannot_modify_accepted_quote(as_user):
    t = ticket("RMC-3")  # accepté dans le seed
    r = as_user("yanis").patch(f"/api/v1/tickets/{t.id}/quote", {"amount_ht": "10"}, format="json")
    assert r.status_code == 400 and r.data["code"] == "quote_locked"


# ---------- Versions (feuille de route) ----------

def test_milestones_crud_is_digitalia_only(as_user):
    julie, sara = as_user("julie"), as_user("sara")
    assert julie.post("/api/v1/projects/SCV/milestones", {"name": "V4"}, format="json").status_code == 403
    r = sara.post("/api/v1/projects/SCV/milestones", {"name": "Version 4.0", "starts_on": "2027-01-01",
                                                     "ends_on": "2027-02-01"}, format="json")
    assert r.status_code == 201 and r.data["order"] == 4
    mid = r.data["id"]
    assert sara.patch(f"/api/v1/projects/SCV/milestones/{mid}", {"name": "V4"}, format="json").data["name"] == "V4"
    assert julie.patch(f"/api/v1/projects/SCV/milestones/{mid}", {"name": "x"}, format="json").status_code == 403
    assert sara.delete(f"/api/v1/projects/SCV/milestones/{mid}").status_code == 204
    names = [m["name"] for m in julie.get("/api/v1/projects/SCV/milestones").data]
    assert names == ["Version 2.3", "Version 2.4", "Version 3.0"]


# ---------- Scénario d'acceptation Sprint 2 ----------

def test_sprint2_acceptance_scenario(as_user):
    """Une évolution sur devis est proposée, acceptée, planifiée."""
    yanis, julie = as_user("yanis"), as_user("julie")
    t = new_evolution(as_user)
    assert triage(yanis, t, decision="analyser", estimate_days="4").status_code == 200
    r = triage(yanis, t, decision="devis", quote=QUOTE, message="Voici notre proposition.")
    assert r.data["status"] == "devis"
    assert julie.post(f"/api/v1/tickets/{t.id}/quote/accept").data["status"] == "faire"
    ms = Milestone.objects.get(project__key="SCV", name="Version 3.0")
    r = yanis.patch(f"/api/v1/tickets/{t.id}", {"milestone": ms.id, "due_on": "2026-11-30"}, format="json")
    assert r.data["milestone"]["name"] == "Version 3.0" and r.data["client_label"] == "Planifiée"
    kinds = [e["kind"] for e in julie.get(f"/api/v1/tickets/{t.id}/events").data]
    assert kinds.index("quote_sent") < kinds.index("quote_accepted")


def test_seed_quotes(seeded):
    assert Quote.objects.get(ticket__project__key="SCV", ticket__number=3).status == "sent"
    rmc = Quote.objects.get(ticket__project__key="RMC", ticket__number=3)
    assert rmc.status == "accepted" and [i.is_paid for i in rmc.installments.all()] == [True, False]
