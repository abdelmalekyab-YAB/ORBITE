"""Facturation branchée sur Orbit, avec des données inventées (aucune donnée réelle dans le dépôt)."""

import json
from datetime import date
from decimal import Decimal

import pytest
from django.core.management import call_command
from django.utils import timezone

from apps.accounts.models import Organization
from apps.billing import models as M
from apps.projects.models import Project

TODAY = date(2026, 10, 25)


@pytest.fixture(autouse=True)
def _today(monkeypatch):
    monkeypatch.setattr(timezone, "localdate", lambda *args, **kwargs: TODAY)


def dashboard(client):
    response = client.get("/api/v1/billing/dashboard/")
    assert response.status_code == 200
    return response.json()


def test_billing_is_admin_only(as_user):
    assert as_user("admin").get("/api/v1/billing/dashboard/").status_code == 200
    for login in ("yanis", "sara", "julie"):  # chef de projet, développeuse, client
        assert as_user(login).get("/api/v1/billing/dashboard/").status_code == 403, login
        assert as_user(login).get("/api/v1/billing/invoices/").status_code == 403, login
        assert as_user(login).get("/api/v1/billing/orbit-projects/").status_code == 403, login


def test_orbit_projects_lists_active_projects_for_admin(as_user, seeded):
    rows = as_user("admin").get("/api/v1/billing/orbit-projects/").json()
    assert rows and {"id", "name", "client_id", "client_name"} <= set(rows[0])


def test_fixed_month_counts_only_once_marked_and_planned_invoices_are_due(as_user, seeded):
    scv = Project.objects.get(key="SCV")
    M.BillingProfile.objects.create(
        project=scv, billing_type="fixed", monthly_amount=Decimal("1000"), start_month="2026-08", status="validated"
    )
    twm = Project.objects.get(key="TWM")
    M.BillingProfile.objects.create(
        project=twm, billing_type="quote", quote_amount=Decimal("5000"), start_month="2026-09", status="validated"
    )
    M.Invoice.objects.create(
        project=twm,
        service_month="2026-09",
        amount=Decimal("2000"),
        status="issued",
        label="Acompte",
        due_date=date(2026, 10, 10),
    )
    M.Invoice.objects.create(
        project=twm, service_month="2026-09", amount=Decimal("1500"), status="planned", label="Situation 2"
    )
    admin = as_user("admin")

    d = dashboard(admin)
    # R2/R8 : août et septembre sont facturés, octobre (mois en cours) ne l'est pas tant qu'il n'est pas marqué.
    assert Decimal(str(d["ytd"])) == Decimal("1000") * 2 + Decimal("2000")
    assert Decimal(str(d["mrr"])) == Decimal("1000")
    # R11 : le fixe d'octobre + la facture prévue en septembre non émise sont « à facturer ».
    assert Decimal(str(d["to_bill_total"])) == Decimal("2500")
    # R15/R16 : l'acompte échu le 10 octobre et non payé est en retard.
    assert Decimal(str(d["cash"]["late_total"])) == Decimal("2000")

    occ = M.FixedOccurrence.objects.create(project=scv, month="2026-10", billed_marked=True)
    d = dashboard(admin)
    assert Decimal(str(d["month_revenue"])) == Decimal("1000")
    assert Decimal(str(d["to_bill_total"])) == Decimal("1500")
    occ.delete()


def test_import_attaches_to_existing_orbit_clients_and_creates_missing_ones(tmp_path, seeded):
    export = {
        "clients": [{"id": "c1", "name": "Client Alpha"}, {"id": "c2", "name": "Nouveau Client"}],
        "projects": [
            {
                "id": "p1",
                "client_id": "c1",
                "name": "Projet Beta",
                "billing_type": "fixed",
                "monthly_amount": 900,
                "start_month": "2026-07",
                "status": "validated",
            },
            {
                "id": "p2",
                "client_id": "c2",
                "name": "Site vitrine",
                "billing_type": "quote",
                "quote_amount": 3000,
                "start_month": "2026-10",
                "status": "proposal",
            },
        ],
        "invoices": [
            {
                "id": "i1",
                "project_id": "p1",
                "service_month": "2026-07",
                "amount": 900,
                "status": "issued",
                "payment": {"status": "paid", "paid_on": "2026-08-05"},
            }
        ],
    }
    path = tmp_path / "export.json"
    path.write_text(json.dumps(export))
    call_command("import_legacy", str(path))
    call_command("import_legacy", str(path))  # idempotent

    alpha = Organization.objects.get(name="Client Alpha", kind=Organization.Kind.CLIENT)
    assert Project.objects.get(name="Projet Beta").client == alpha  # rapproché, pas dupliqué
    created = Project.objects.get(name="Site vitrine")
    assert created.client.name == "Nouveau Client" and created.key  # nouveau projet Orbit avec une clé
    assert M.BillingProfile.objects.count() == 2
    assert M.Invoice.objects.get(legacy_id="i1").payment_status == "paid"
