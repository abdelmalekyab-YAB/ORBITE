"""
Contrôle post-import : recalcule les totaux depuis la base Orbit et les compare
à data/reference_totals.json (chiffres de la plateforme au 25/10/2026).

    python manage.py check_reference data/reference_totals.json
"""

import json
from datetime import date
from decimal import Decimal
from pathlib import Path

from django.core.management.base import BaseCommand

from apps.billing.services.billing import BillingEngine, load_snapshot


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument("reference_json")

    def handle(self, *args, **opts):
        ref = json.loads(Path(opts["reference_json"]).read_text(encoding="utf-8"))
        e = BillingEngine(load_snapshot(), today=date.fromisoformat(ref["as_of_date"]))

        def q(v):
            return Decimal(str(v)).quantize(Decimal("0.01"))

        errors = 0

        def check(label, got, exp):
            nonlocal errors
            if q(got) != q(exp):
                errors += 1
                self.stdout.write(self.style.ERROR(f"  ✗ {label}: attendu {q(exp)} · obtenu {q(got)}"))

        # Les ids legacy → ids Orbit : on compare par nom de projet / client
        by_name = {p.name: p for p in e.s.projects}
        for m, exp in ref["months"].items():
            check(f"CA {m}", e.month_totals(m).revenue, exp["ca"])
        for _pid, exp in ref["projects"].items():
            p = by_name.get(exp["name"])
            if not p:
                errors += 1
                self.stdout.write(self.style.ERROR(f"  ✗ projet absent : {exp['name']}"))
                continue
            check(f"facturé {p.name}", e.billed_to_date(p), exp["billed"])
            check(f"planifié {p.name}", e.planned_of(p), exp["planned"])
        c = e.cash_summary()
        check("encaissements en retard", c["late_total"], ref["cash"]["late"])
        check("encaissements ce mois", c["this_month_total"], ref["cash"]["this_month"])
        check("encaissements mois suivants", c["later_total"], ref["cash"]["later"])
        check("MRR", e.mrr(), ref["mrr"])
        check("cumul année", e.year_to_date(), ref["ytd"])
        if errors:
            self.stdout.write(self.style.ERROR(f"{errors} écart(s) — ne pas basculer avant correction."))
        else:
            self.stdout.write(self.style.SUCCESS("Tous les totaux correspondent à la plateforme. Bascule possible."))
