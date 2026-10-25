"""
Client Zoho Books — LECTURE SEULE (SPEC §9, règle absolue).

Ce module n'expose QUE des méthodes de lecture. Aucune méthode create/update/delete/
email/mark ne doit y être ajoutée. Un test (tests/test_zoho_readonly.py) vérifie
qu'aucune requête POST/PUT/DELETE n'est émise.

Paramètres (settings.py) :
    ZOHO_BOOKS = {
        "ORGANIZATION_ID": env("ZOHO_ORGANIZATION_ID"),
        "API_BASE": "https://www.zohoapis.com/books/v3",     # région .com
        "ACCOUNTS_BASE": "https://accounts.zoho.com",
        "CLIENT_ID": env("ZOHO_CLIENT_ID"), "CLIENT_SECRET": env("ZOHO_CLIENT_SECRET"),
        "REFRESH_TOKEN": env("ZOHO_REFRESH_TOKEN"),
        # scopes : ZohoBooks.invoices.READ, ZohoBooks.contacts.READ, ZohoBooks.customerpayments.READ
    }
Le refresh token s'obtient une fois via la console https://api-console.zoho.com (Self Client).
"""

from __future__ import annotations

import time
from datetime import date

import requests
from django.conf import settings

ALLOWED_METHODS = {"GET"}


class ZohoReadOnlyClient:
    def __init__(self):
        cfg = settings.ZOHO_BOOKS
        self.org = cfg["ORGANIZATION_ID"]
        self.base = cfg.get("API_BASE", "https://www.zohoapis.com/books/v3")
        self.accounts = cfg.get("ACCOUNTS_BASE", "https://accounts.zoho.com")
        self.cfg = cfg
        self._token, self._exp = None, 0

    def _access_token(self) -> str:
        if self._token and time.time() < self._exp - 60:
            return self._token
        r = requests.post(
            f"{self.accounts}/oauth/v2/token",
            data={
                "refresh_token": self.cfg["REFRESH_TOKEN"],
                "client_id": self.cfg["CLIENT_ID"],
                "client_secret": self.cfg["CLIENT_SECRET"],
                "grant_type": "refresh_token",
            },
            timeout=30,
        )
        r.raise_for_status()
        j = r.json()
        self._token, self._exp = j["access_token"], time.time() + int(j.get("expires_in", 3600))
        return self._token

    def _get(self, path: str, **params) -> dict:
        # Garde-fou : ce client ne fait QUE du GET.
        method = "GET"
        assert method in ALLOWED_METHODS
        params["organization_id"] = self.org
        r = requests.request(
            method,
            f"{self.base}/{path}",
            params=params,
            timeout=60,
            headers={"Authorization": f"Zoho-oauthtoken {self._access_token()}"},
        )
        if r.status_code == 429:
            time.sleep(60)
            return self._get(path, **params)
        r.raise_for_status()
        return r.json()

    # ---- lectures ----
    def list_invoices(self, **filters) -> list[dict]:
        out, page = [], 1
        while True:
            j = self._get("invoices", page=page, per_page=200, **filters)
            out += j.get("invoices", [])
            if not j.get("page_context", {}).get("has_more_page"):
                return out
            page += 1

    def get_invoice(self, invoice_id: str) -> dict:
        return self._get(f"invoices/{invoice_id}").get("invoice", {})

    def list_contacts(self) -> list[dict]:
        return self._get("contacts", per_page=200).get("contacts", [])

    def list_customer_payments(self, **filters) -> list[dict]:
        return self._get("customerpayments", per_page=200, **filters).get("customerpayments", [])


def zoho_to_payment(z: dict) -> dict:
    """Mappe une facture Zoho vers (payment_status, due_date, paid_on)."""
    st = z.get("status")
    if st == "paid" or float(z.get("balance", 1)) == 0:
        return {
            "payment_status": "paid",
            "due_date": z.get("due_date") or None,
            "paid_on": z.get("last_payment_date") or z.get("due_date") or None,
        }
    if st == "overdue":
        return {"payment_status": "late", "due_date": z.get("due_date") or None, "paid_on": None}
    return {"payment_status": "pending", "due_date": z.get("due_date") or None, "paid_on": None}


def sync_payment_statuses():
    """
    Pour chaque facture Orbit avec un invoice_number : lit Zoho et met à jour le paiement.
    Remonte les incohérences (montant, brouillon, annulée, absente) sans rien corriger.
    """
    from apps.billing import models as M

    log = M.ZohoSyncLog()
    try:
        client = ZohoReadOnlyClient()
        zoho = {z["invoice_number"].strip(): z for z in client.list_invoices()}
        issues, updated = [], 0
        for inv in M.Invoice.objects.exclude(invoice_number="").filter(status=M.Invoice.ISSUED):
            z = zoho.get(inv.invoice_number)
            if not z:
                issues.append({"invoice_number": inv.invoice_number, "issue": "absente_zoho", "detail": inv.label})
                continue
            if abs(float(z["total"]) - float(inv.amount)) > 0.01:
                issues.append(
                    {
                        "invoice_number": inv.invoice_number,
                        "issue": "montant_different",
                        "detail": f"Orbit {inv.amount} · Zoho {z['total']}",
                    }
                )
            if z["status"] in ("draft", "void"):
                issues.append(
                    {"invoice_number": inv.invoice_number, "issue": z["status"], "detail": z.get("customer_name", "")}
                )
                continue
            pay = zoho_to_payment(z)
            changed = any(str(getattr(inv, k) or "") != str(v or "") for k, v in pay.items())
            if changed:
                for k, v in pay.items():
                    setattr(inv, k, date.fromisoformat(v) if (k != "payment_status" and v) else v)
                inv.zoho_invoice_id = z.get("invoice_id", "")
                inv.save(update_fields=["payment_status", "due_date", "paid_on", "zoho_invoice_id"])
                updated += 1
        # Factures Zoho récentes absentes d'Orbit, pour les clients suivis seulement
        tracked = set(M.BillingProfile.objects.values_list("project__client__name", flat=True))
        for num, z in zoho.items():
            if (
                z.get("customer_name") in tracked
                and z["status"] not in ("draft", "void")
                and not M.Invoice.objects.filter(invoice_number=num).exists()
            ):
                issues.append(
                    {
                        "invoice_number": num,
                        "issue": "absente_orbit",
                        "detail": f"{z.get('customer_name')} · {z.get('date')} · {z.get('total')} €",
                    }
                )
        log.updated_count, log.issues = updated, issues
    except Exception as exc:  # noqa: BLE001
        log.ok, log.error = False, str(exc)
    log.save()
    return log
