"""Règles 19 à 22 (finances) et critère du Sprint 3 : les chiffres de la maquette sont reproduits par le seed."""
from datetime import date
from decimal import Decimal

import pytest
from django.utils import timezone

from apps.finance import service
from apps.finance.models import ProjectFinance
from apps.projects.models import Project
from apps.tickets.models import Quote, Ticket, TicketEvent

TODAY = date(2026, 9, 29)  # « aujourd'hui » de la maquette


@pytest.fixture(autouse=True)
def frozen_today(monkeypatch):
    monkeypatch.setattr(timezone, "localdate", lambda *a, **k: TODAY)


def P(key):
    return Project.objects.get(key=key)


def D(v):
    return Decimal(str(v))


# ---------- Critère Sprint 3 : chiffres de la maquette ----------

@pytest.mark.parametrize("key,expected", [
    ("SCV", dict(dev_paid=12600, dev_left=5400, licence=1780, licence_months=2, quotes_paid=0, pending_quotes=3600,
                 total=14380, to_come=5400, cost=13800, margin=580, has_cost=True)),
    ("RMC", dict(dev_paid=9500, dev_left=0, licence=1770, licence_months=3, quotes_paid=1450, quotes_left=1450,
                 quotes_count=1, total=12720, to_come=1450, cost=3600, margin=9120)),
    ("TWM", dict(dev_paid=25600, dev_left=6400, licence=5160, licence_months=4, total=30760, to_come=6400,
                 cost=50400, margin=-19640)),
    ("CHK", dict(dev_paid=6000, dev_left=6000, licence=450, licence_months=1, total=6450, has_cost=False, cost=0)),
])
def test_summary_matches_maquette(seeded, key, expected):
    s = service.summary(P(key), TODAY)
    for field, value in expected.items():
        assert s[field] == (value if isinstance(value, bool) else D(value)) or s[field] == value, (field, s[field])


@pytest.mark.parametrize("key,month,expected", [
    ("SCV", date(2026, 10, 1), 6290),   # échéance dev 5 400 + licence 890
    ("SCV", date(2026, 7, 1), 7200),    # licence pas encore commencée
    ("RMC", date(2026, 11, 1), 2040),   # licence 590 + échéance de devis accepté 1 450
    ("TWM", date(2026, 3, 1), 9600),
    ("CHK", date(2026, 12, 1), 6450),
    ("CHK", date(2027, 6, 1), 450),     # projection : licence sans fin
])
def test_revenue_by_month(seeded, key, month, expected):
    assert service.revenue(P(key), month) == D(expected)


@pytest.mark.parametrize("key,month,expected", [
    ("TWM", date(2026, 3, 1), 50400),  # 112 j × 450 € comptabilisés en mars
    ("TWM", date(2026, 4, 1), 0),
    ("SCV", date(2026, 4, 1), 0),      # avant le début du projet
    ("SCV", date(2026, 5, 1), 2760),   # Sara 30 % de 3 600 + Yanis 40 % de 4 200
    ("RMC", date(2026, 5, 1), 0),
    ("RMC", date(2026, 6, 1), 900),
    ("CHK", date(2026, 9, 1), 0),
])
def test_cost_by_mode(seeded, key, month, expected):
    assert service.cost(P(key), month) == D(expected)


# ---------- Règles 19-20 ----------

def test_costs_are_optional(seeded):
    ProjectFinance.objects.filter(project__key="RMC").update(cost_mode="none")
    s = service.summary(P("RMC"), TODAY)
    assert s["has_cost"] is False and s["cost"] == 0 and s["margin"] == s["total"]


def test_licence_stops_at_licence_end(seeded):
    fin = service.finance_of(P("SCV"))
    fin.licence_end = date(2026, 8, 1)
    fin.save()
    assert service.revenue(P("SCV"), date(2026, 9, 1)) == 0
    assert service.summary(P("SCV"), TODAY)["licence_months"] == 1


def test_accepted_quote_feeds_revenue(seeded, as_user):
    t = Ticket.objects.get(project__key="SCV", number=3)
    as_user("julie").post(f"/api/v1/tickets/{t.id}/quote/accept")
    assert service.revenue(P("SCV"), date(2026, 9, 1)) == D(890 + 1800)
    s = service.summary(P("SCV"), TODAY)
    assert s["quotes_left"] == D(3600) and s["pending_quotes"] == 0


# ---------- Règle 21 : affectations > 100 % = avertissement, pas blocage ----------

def test_staff_over_allocation_warns_but_saves(as_user):
    admin = as_user("admin")
    sara = next(r for r in admin.get("/api/v1/finance/staff").data if r["name"] == "Sara Dev")
    assert sara["total"] == 100 and sara["warning"] is None
    r = admin.put("/api/v1/finance/staff", [{"user": sara["user"], "monthly_salary": "3800",
                                             "allocations": {"SCV": 60, "TWM": 50, "RMC": 20}}], format="json")
    assert r.status_code == 200
    row = next(x for x in r.data if x["user"] == sara["user"])
    assert row["total"] == 130 and row["warning"] and row["monthly_salary"] == "3800.00"
    assert service.people_cost(P("SCV")) == D(3800 * 0.6 + 4200 * 0.4)


# ---------- Règle 22 : estimations = aide au chiffrage, jamais des recettes ----------

def test_estimates_never_enter_revenue(seeded, as_user):
    before = service.revenue(P("SCV"), date(2026, 9, 1))
    Ticket.objects.filter(project__key="SCV", number=9).update(estimate_days=Decimal("10"))
    assert service.revenue(P("SCV"), date(2026, 9, 1)) == before
    data = as_user("admin").get("/api/v1/finance/overview").data
    row = next(r for r in data["to_quote"] if r["ref"] == "SCV-9")
    assert row["potential"] == "4500.00"  # 10 j × TJM 450


# ---------- API ----------

@pytest.mark.parametrize("login", ["yanis", "sara", "julie"])
def test_finance_is_admin_only(as_user, login):
    c = as_user(login)
    for url in ("/api/v1/finance/overview", "/api/v1/finance/projects/SCV", "/api/v1/finance/staff"):
        assert c.get(url).status_code == 403


def test_settings_readable_by_pm_writable_by_admin(as_user):
    assert as_user("yanis").get("/api/v1/finance/settings").data["default_tjm"] == "450.00"
    assert as_user("yanis").put("/api/v1/finance/settings", {"default_tjm": "500"}, format="json").status_code == 403
    assert as_user("julie").get("/api/v1/finance/settings").status_code == 403
    r = as_user("admin").put("/api/v1/finance/settings", {"default_tjm": "500"}, format="json")
    assert r.data["default_tjm"] == "500.00"


def test_overview(as_user):
    data = as_user("admin").get("/api/v1/finance/overview").data
    assert data["current"] == "2026-09" and len(data["months"]) == 12 and data["has_cost"] is True
    sept = next(m for m in data["months"] if m["month"] == "2026-09")
    # Septembre : licences SCV 890 + RMC 590 + TWM 1 290 + CHK 450 + échéance devis RMC 1 450
    assert sept["total"] == "4670.00"
    assert data["kpis"]["licence_monthly"] == "3220.00"
    assert data["kpis"]["dev_to_come"] == "17800.00"  # 5 400 + 6 400 + 6 000
    assert {p["key"]: p["total"] for p in data["projects"]} == {
        "CHK": "6450.00", "RMC": "12720.00", "SCV": "14380.00", "TWM": "30760.00"}
    assert as_user("admin").get("/api/v1/finance/overview?from=2026-01&to=2026-03").data["months"][2]["total"] == "9600.00"


def test_project_finance_update_and_installments(as_user):
    admin = as_user("admin")
    r = admin.put("/api/v1/finance/projects/CHK", {"licence_amount": "500", "licence_start": "2026-10",
                                                   "cost_mode": "monthly", "cost_monthly": "300"}, format="json")
    assert r.status_code == 200 and r.data["licence_start"] == "2026-10" and r.data["summary"]["has_cost"] is True
    r = admin.post("/api/v1/finance/projects/CHK/installments", {"due_on": "2027-01-15", "amount": "2000"}, format="json")
    assert r.status_code == 201
    iid = r.data["id"]
    r = admin.patch(f"/api/v1/finance/projects/CHK/installments/{iid}", {"is_paid": True}, format="json")
    assert r.data["is_paid"] and r.data["paid_on"] == "2026-09-29"
    assert admin.post("/api/v1/finance/projects/CHK/installments", {"due_on": "2027-01-15", "amount": "0"},
                      format="json").status_code == 400
    assert admin.delete(f"/api/v1/finance/projects/CHK/installments/{iid}").status_code == 204
    assert admin.put("/api/v1/finance/projects/CHK", {"licence_start": "bad"}, format="json").status_code == 400


def test_mark_quote_installment_paid(as_user):
    q = Quote.objects.get(ticket__project__key="RMC", ticket__number=3)
    inst = q.installments.get(is_paid=False)
    r = as_user("admin").patch(f"/api/v1/finance/quotes/{q.id}/installments/{inst.id}", {"is_paid": True}, format="json")
    assert r.status_code == 200
    s = service.summary(P("RMC"), TODAY)
    assert s["quotes_paid"] == D(2900) and s["quotes_left"] == 0
    assert TicketEvent.objects.filter(ticket=q.ticket, kind="quote_installment").exists()
    assert as_user("yanis").patch(f"/api/v1/finance/quotes/{q.id}/installments/{inst.id}", {"is_paid": False},
                                  format="json").status_code == 403


def test_client_never_sees_finance_fields(as_user):
    data = as_user("julie").get("/api/v1/projects/SCV").data
    assert not {"dev_price", "licence_amount", "summary"} & set(data)
