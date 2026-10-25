"""
Import de l'export de la plateforme actuelle dans Orbit.

    python manage.py import_legacy data/export_plateforme.json --documents data/documents
    python manage.py import_legacy data/export_plateforme.json --dry-run

Idempotent : relancer la commande met à jour les objets existants (clé `legacy_id`)
au lieu de les dupliquer. Les clients/projets sont rapprochés par NOM avec les
objets Orbit existants ; s'ils n'existent pas, ils sont créés.

Après l'import, lancer :  python manage.py check_reference data/reference_totals.json
"""

from __future__ import annotations

import json
from datetime import date
from decimal import Decimal
from pathlib import Path

from django.apps import apps
from django.core.files import File
from django.core.management.base import BaseCommand
from django.db import transaction

from apps.billing import models as M


def pd(s):
    return date.fromisoformat(s) if s else None


class Command(BaseCommand):
    help = "Importe export_plateforme.json (clients, projets, factures, paiements, dépenses, documents)."

    def add_arguments(self, parser):
        parser.add_argument("export_json")
        parser.add_argument("--documents", default=None, help="Dossier contenant les PDF (data/documents)")
        parser.add_argument("--dry-run", action="store_true")

    def handle(self, *args, **opts):
        data = json.loads(Path(opts["export_json"]).read_text(encoding="utf-8"))
        docs_dir = Path(opts["documents"]) if opts["documents"] else Path(opts["export_json"]).parent
        ClientModel = apps.get_model(M.CLIENT_MODEL)
        ProjectModel = apps.get_model(M.PROJECT_MODEL)
        stats = {k: 0 for k in ["clients", "projects", "profiles", "invoices", "occurrences", "expenses", "documents"]}

        with transaction.atomic():
            # --- clients (rapprochement par nom) ---
            cmap = {}
            for c in data["clients"]:
                obj = ClientModel.objects.filter(name=c["name"], kind=ClientModel.Kind.CLIENT).first()
                created = obj is None
                if created:
                    obj = ClientModel.objects.create(name=c["name"], kind=ClientModel.Kind.CLIENT)
                if hasattr(obj, "legacy_id") and not obj.legacy_id:
                    obj.legacy_id = c["id"]
                    obj.save(update_fields=["legacy_id"])
                cmap[c["id"]] = obj
                stats["clients"] += int(created)

            # --- projets + profils ---
            pmap = {}
            for p in data["projects"]:
                client = cmap[p["client_id"]]
                obj = ProjectModel.objects.filter(client=client, name=p["name"]).first()
                created = obj is None
                if created:
                    obj = ProjectModel.objects.create(
                        client=client, name=p["name"], key=self._new_key(ProjectModel, p["name"])
                    )
                if hasattr(obj, "legacy_id") and not obj.legacy_id:
                    obj.legacy_id = p["id"]
                    obj.save(update_fields=["legacy_id"])
                pmap[p["id"]] = obj
                stats["projects"] += int(created)
                bp, _ = M.BillingProfile.objects.update_or_create(
                    project=obj,
                    defaults={
                        "billing_type": p["billing_type"],
                        "monthly_amount": Decimal(str(p.get("monthly_amount") or 0)),
                        "quote_amount": Decimal(str(p["quote_amount"])) if p.get("quote_amount") else None,
                        "cost": Decimal(str(p.get("cost") or 0)),
                        "start_month": p["start_month"],
                        "end_month": p.get("end_month") or "",
                        "status": p["status"],
                        "note": p.get("note", ""),
                    },
                )
                stats["profiles"] += 1
                for d in p.get("documents", []):
                    if d.get("file") and not bp.documents.filter(file__endswith=Path(d["file"]).name).exists():
                        self._attach(bp.documents, docs_dir / d["file"], kind=d.get("kind", ""), stats=stats)

            # --- factures ---
            for i in data["invoices"]:
                pay = i.get("payment") or {}
                inv, _ = M.Invoice.objects.update_or_create(
                    legacy_id=i["id"],
                    defaults={
                        "project": pmap[i["project_id"]],
                        "service_month": i["service_month"],
                        "amount": Decimal(str(i["amount"])),
                        "label": i.get("label", ""),
                        "kind": i.get("kind", "invoice"),
                        "status": i["status"],
                        "due_date": pd(pay.get("due_date")),
                        "payment_status": pay.get("status", "pending"),
                        "paid_on": pd(pay.get("paid_on")),
                    },
                )
                stats["invoices"] += 1
                if i.get("document") and not inv.document:
                    self._attach_field(inv, "document", "document_name", docs_dir / i["document"], stats)

            # --- occurrences fixes : ajustements, marques, paiements, documents ---
            def occ(pid, month):
                return M.FixedOccurrence.objects.get_or_create(project=pmap[pid], month=month)[0]

            for o in data.get("fixed_overrides", []):
                x = occ(o["project_id"], o["month"])
                x.override_amount = Decimal(str(o["amount"]))
                x.save()
                stats["occurrences"] += 1
            for o in data.get("fixed_billed_marks", []):
                x = occ(o["project_id"], o["month"])
                x.billed_marked = True
                x.save()
                stats["occurrences"] += 1
            for o in data.get("payments", []):
                x = occ(o["project_id"], o["month"])
                if o["ref"] == "fixed":
                    x.payment_status = o.get("status", "pending")
                    x.due_date = pd(o.get("due_date"))
                    x.paid_on = pd(o.get("paid_on"))
                    x.save()
                elif o["ref"] == "fixed_document" and o.get("document") and not x.document:
                    self._attach_field(x, "document", "document_name", docs_dir / o["document"], stats)
                stats["occurrences"] += 1

            # --- dépenses ---
            for x in data.get("expenses", []):
                M.Expense.objects.update_or_create(
                    legacy_id=x["id"],
                    defaults={
                        "date": pd(x["date"]),
                        "supplier": x["supplier"],
                        "category": x.get("category", "Autres"),
                        "label": x.get("label", ""),
                        "project": pmap.get(x.get("projectId") or x.get("project_id") or ""),
                        "amount_ht": Decimal(str(x.get("ht") or x.get("amount_ht") or 0)),
                        "vat": Decimal(str(x.get("tva") or x.get("vat") or 0)),
                    },
                )
                stats["expenses"] += 1

            if opts["dry_run"]:
                transaction.set_rollback(True)
                self.stdout.write(self.style.WARNING("DRY RUN — rien n'a été enregistré."))

        for k, v in stats.items():
            self.stdout.write(f"  {k:12s} {v}")
        self.stdout.write(self.style.SUCCESS("Import terminé."))

    # --- helpers ---
    @staticmethod
    def _new_key(ProjectModel, name: str) -> str:
        """Orbit projects need a short unique key (ticket references): built from the name's initials."""
        import re

        words = re.findall(r"[A-Za-z0-9]+", name.upper())
        base = ("".join(w[0] for w in words) if len(words) > 1 else (words[0] if words else "PRJ"))[:4] or "PRJ"
        key, n = base, 2
        while ProjectModel.objects.filter(key=key).exists():
            key, n = f"{base[:4]}{n}"[:6], n + 1
        return key

    def _attach(self, manager, path: Path, kind: str, stats: dict):
        if not path.exists():
            self.stdout.write(self.style.WARNING(f"  document manquant : {path}"))
            return
        with path.open("rb") as fh:
            manager.create(
                kind=kind, file=File(fh, name=path.name), original_name=path.name.split("_", 1)[-1]
            )  # le fichier garde le nom <hash>_<nom> → test de doublon fiable
        stats["documents"] += 1

    def _attach_field(self, obj, field: str, name_field: str, path: Path, stats: dict):
        if not path.exists():
            self.stdout.write(self.style.WARNING(f"  document manquant : {path}"))
            return
        with path.open("rb") as fh:
            getattr(obj, field).save(path.name, File(fh), save=False)
        setattr(obj, name_field, path.name.split("_", 1)[-1])
        obj.save()
        stats["documents"] += 1
