"""
Test d'or : le moteur Python doit reproduire exactement les totaux calculés par la
plateforme actuelle au 25/10/2026 (data/reference_totals.json), à partir de
data/export_plateforme.json. Aucune base de données nécessaire.

Ces données sont confidentielles : elles ne sont jamais dans le dépôt. Le test lit le dossier indiqué par
ORBIT_FINANCE_DATA (export_plateforme.json + reference_totals.json) et ne s'exécute que s'il est fourni :
    ORBIT_FINANCE_DATA=/chemin/vers/data pytest apps/billing/tests/test_reference.py
"""

import json
import os
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from apps.billing.services.billing import BillingEngine, month_range, snapshot_from_export

DATA = Path(os.environ.get("ORBIT_FINANCE_DATA", "/nonexistent"))
pytestmark = pytest.mark.skipif(
    not (DATA / "reference_totals.json").exists(),
    reason="données financières confidentielles non fournies (ORBIT_FINANCE_DATA)",
)


@pytest.fixture(scope="module")
def ref():
    return json.loads((DATA / "reference_totals.json").read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def engine(ref):
    data = json.loads((DATA / "export_plateforme.json").read_text(encoding="utf-8"))
    return BillingEngine(snapshot_from_export(data), today=date.fromisoformat(ref["as_of_date"]))


def dec(v):
    return Decimal(str(v)).quantize(Decimal("0.01"))


def test_month_revenue_matches_platform(engine, ref):
    for m, exp in ref["months"].items():
        t = engine.month_totals(m)
        assert dec(t.revenue) == dec(exp["ca"]), m
        assert dec(t.fixed) == dec(exp["fixe"]), m
        assert dec(t.quote) == dec(exp["devis"]), m


def test_projects_billed_and_remaining(engine, ref):
    for pid, exp in ref["projects"].items():
        p = engine.project(pid)
        assert p is not None, pid
        assert dec(engine.billed_to_date(p)) == dec(exp["billed"]), p.name
        assert dec(engine.planned_of(p)) == dec(exp["planned"]), p.name
        assert dec(engine.fixed_to_bill(p, engine.now)) == dec(exp["to_bill_now"]), p.name


def test_clients_totals(engine, ref):
    first = engine.first_month()
    for cid, exp in ref["clients"].items():
        total = sum(
            (
                engine.project_month(p, m).revenue
                for m in month_range(first, engine.now)
                for p in engine.s.projects
                if p.client_id == cid
            ),
            Decimal(0),
        )
        assert dec(total) == dec(exp["total"]), exp["name"]


def test_cash_summary(engine, ref):
    c = engine.cash_summary()
    assert dec(c["late_total"]) == dec(ref["cash"]["late"])
    assert dec(c["this_month_total"]) == dec(ref["cash"]["this_month"])
    assert dec(c["later_total"]) == dec(ref["cash"]["later"])
    assert dec(c["no_due_total"]) == dec(ref["cash"]["no_due"])
    assert dec(c["total"]) == dec(ref["cash"]["total"])


def test_due_and_billed_this_month(engine, ref):
    due = engine.due_items()
    fixed = sum((d.amount for d in due if d.key.startswith("fix:")), Decimal(0))
    planned = sum((d.amount for d in due if d.key.startswith("inv:")), Decimal(0))
    assert dec(fixed) == dec(ref["due"]["fixed_to_bill"])
    assert dec(planned) == dec(ref["due"]["planned_due"])
    billed_m = sum((x.amount for x in engine.billed_items() if x.month == engine.now), Decimal(0))
    assert dec(billed_m) == dec(ref["due"]["billed_this_month"])


def test_mrr_and_ytd(engine, ref):
    assert dec(engine.mrr()) == dec(ref["mrr"])
    assert dec(engine.year_to_date()) == dec(ref["ytd"])


def test_forecast_7421_unique_per_month(engine):
    seen = set()
    for i in engine.s.invoices:
        if i.kind == "forecast_7421":
            assert (i.project_id, i.service_month) not in seen
            seen.add((i.project_id, i.service_month))
