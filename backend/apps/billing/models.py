"""
Facturation de DIGITALIA (module Finance migré de la plateforme interne) — modèles.

Branché sur les clients (`accounts.Organization`) et projets (`projects.Project`) d'Orbit :
un projet reçoit un profil de facturation, ses factures, ses paiements, ses documents.
Réservé à l'administration. Montants en euros HT. Voir docs/09-facturation.md.
"""

from __future__ import annotations

import re
from decimal import Decimal

from django.core.validators import RegexValidator
from django.db import models

MONTH_RE = RegexValidator(r"^\d{4}-(0[1-9]|1[0-2])$", "Format attendu : YYYY-MM")
CLIENT_MODEL = "accounts.Organization"
PROJECT_MODEL = "projects.Project"


def upload_to(instance, filename):
    return f"finance/{instance.__class__.__name__.lower()}/{filename}"


# ---------------------------------------------------------------------------
# Profil de facturation d'un projet (SPEC §3.2)
# ---------------------------------------------------------------------------
class BillingProfile(models.Model):
    FIXED, QUOTE = "fixed", "quote"
    TYPES = [(FIXED, "Montant fixe mensuel"), (QUOTE, "Sur devis")]
    VALIDATED, PROPOSAL = "validated", "proposal"
    STATUSES = [(VALIDATED, "Validé"), (PROPOSAL, "Proposition non validée")]

    project = models.OneToOneField(PROJECT_MODEL, on_delete=models.CASCADE, related_name="billing")
    billing_type = models.CharField(max_length=8, choices=TYPES)
    monthly_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    quote_amount = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    cost = models.DecimalField(
        max_digits=12, decimal_places=2, default=0, help_text="Fixe : coût mensuel · Devis : coût total"
    )
    start_month = models.CharField(max_length=7, validators=[MONTH_RE])
    end_month = models.CharField(max_length=7, validators=[MONTH_RE], blank=True, default="")
    status = models.CharField(max_length=10, choices=STATUSES, default=VALIDATED)
    note = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["project__name"]

    def __str__(self):
        return f"{self.project} ({self.get_billing_type_display()})"

    @property
    def is_proposal(self) -> bool:
        return self.status == self.PROPOSAL

    @property
    def is_fixed(self) -> bool:
        return self.billing_type == self.FIXED

    def active_in(self, month: str) -> bool:  # R1
        return self.start_month <= month and (not self.end_month or month <= self.end_month)


class ProjectDocument(models.Model):
    """Devis, proposition, bon de commande… rattachés au projet."""

    profile = models.ForeignKey(BillingProfile, on_delete=models.CASCADE, related_name="documents")
    kind = models.CharField(max_length=80, blank=True, default="")
    file = models.FileField(upload_to=upload_to)
    original_name = models.CharField(max_length=255)
    uploaded_at = models.DateTimeField(auto_now_add=True)


# ---------------------------------------------------------------------------
# Paiement (mixin commun facture / occurrence fixe) — SPEC R15
# ---------------------------------------------------------------------------
class PaymentMixin(models.Model):
    PENDING, LATE, PAID = "pending", "late", "paid"
    PAYMENT_STATUSES = [(PENDING, "En attente"), (LATE, "En retard"), (PAID, "Payé")]

    due_date = models.DateField(null=True, blank=True)
    payment_status = models.CharField(max_length=8, choices=PAYMENT_STATUSES, default=PENDING)
    paid_on = models.DateField(null=True, blank=True)

    class Meta:
        abstract = True

    def payment_state(self, today) -> str:
        """'paid' | 'late' | 'due' (échéance future) | 'wait' (sans échéance)."""
        if self.payment_status == self.PAID:
            return "paid"
        if self.payment_status == self.LATE or (self.due_date and self.due_date < today):
            return "late"
        return "due" if self.due_date else "wait"


# ---------------------------------------------------------------------------
# Facture (SPEC §3.3)
# ---------------------------------------------------------------------------
class Invoice(PaymentMixin):
    INVOICE, DEPOSIT, FORECAST_7421 = "invoice", "deposit", "forecast_7421"
    KINDS = [(INVOICE, "Facture"), (DEPOSIT, "Payé au démarrage"), (FORECAST_7421, "CA prévu 74+21")]
    PLANNED, ISSUED = "planned", "issued"
    STATUSES = [(PLANNED, "Prévue"), (ISSUED, "Émise")]

    legacy_id = models.CharField(max_length=32, blank=True, db_index=True)
    project = models.ForeignKey(PROJECT_MODEL, on_delete=models.CASCADE, related_name="invoices")
    service_month = models.CharField(max_length=7, validators=[MONTH_RE], db_index=True)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    label = models.CharField(max_length=300, blank=True, default="")
    kind = models.CharField(max_length=16, choices=KINDS, default=INVOICE)
    status = models.CharField(max_length=8, choices=STATUSES, default=ISSUED)
    invoice_number = models.CharField(max_length=40, blank=True, default="", db_index=True)
    po_number = models.CharField(max_length=80, blank=True, default="")
    issued_on = models.DateField(null=True, blank=True)
    document = models.FileField(upload_to=upload_to, null=True, blank=True)
    document_name = models.CharField(max_length=255, blank=True, default="")
    zoho_invoice_id = models.CharField(max_length=40, blank=True, default="", db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-service_month", "-created_at"]
        constraints = [
            # une seule ligne « CA prévu 74+21 » par projet et par mois (SPEC §7.3)
            models.UniqueConstraint(
                fields=["project", "service_month"],
                condition=models.Q(kind="forecast_7421"),
                name="unique_forecast_7421_per_month",
            ),
            # un seul « payé au démarrage » par projet (SPEC R20)
            models.UniqueConstraint(
                fields=["project"], condition=models.Q(kind="deposit"), name="unique_deposit_per_project"
            ),
        ]

    def __str__(self):
        return f"{self.project} · {self.service_month} · {self.amount} €"

    def save(self, *args, **kwargs):
        # Extraction automatique du n° de facture depuis le libellé si absent (données historiques)
        if not self.invoice_number:
            m = re.search(r"Facture\s+(\d{6})", self.label or "")
            if m:
                self.invoice_number = m.group(1)
        super().save(*args, **kwargs)

    @property
    def is_planned(self) -> bool:
        return self.status == self.PLANNED


# ---------------------------------------------------------------------------
# Occurrence fixe mensuelle (SPEC §3.4)
# ---------------------------------------------------------------------------
class FixedOccurrence(PaymentMixin):
    project = models.ForeignKey(PROJECT_MODEL, on_delete=models.CASCADE, related_name="fixed_occurrences")
    month = models.CharField(max_length=7, validators=[MONTH_RE])
    override_amount = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    billed_marked = models.BooleanField(default=False)
    document = models.FileField(upload_to=upload_to, null=True, blank=True)
    document_name = models.CharField(max_length=255, blank=True, default="")

    class Meta:
        unique_together = [("project", "month")]
        ordering = ["-month"]

    def __str__(self):
        return f"{self.project} · {self.month}"


# ---------------------------------------------------------------------------
# Dépenses (SPEC §3.5)
# ---------------------------------------------------------------------------
class Expense(models.Model):
    CATEGORIES = [
        (c, c)
        for c in [
            "Sous-traitance",
            "Logiciels & abonnements",
            "Hébergement & serveurs",
            "Matériel informatique",
            "Télécom & internet",
            "Déplacements",
            "Repas & réceptions",
            "Honoraires (comptable, juridique)",
            "Frais bancaires",
            "Marketing & communication",
            "Formation",
            "Fournitures",
            "Autres",
        ]
    ]

    legacy_id = models.CharField(max_length=32, blank=True, db_index=True)
    date = models.DateField(db_index=True)
    supplier = models.CharField(max_length=200)
    category = models.CharField(max_length=60, choices=CATEGORIES, default="Autres")
    label = models.CharField(max_length=300, blank=True, default="")
    project = models.ForeignKey(
        PROJECT_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="expenses"
    )
    amount_ht = models.DecimalField(max_digits=12, decimal_places=2)
    vat = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    receipt = models.FileField(upload_to=upload_to, null=True, blank=True)
    receipt_name = models.CharField(max_length=255, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-date"]

    @property
    def month(self) -> str:
        return self.date.strftime("%Y-%m")

    @property
    def amount_ttc(self) -> Decimal:
        return (self.amount_ht or 0) + (self.vat or 0)


# ---------------------------------------------------------------------------
# Journal de synchronisation Zoho (lecture seule) — SPEC §9
# ---------------------------------------------------------------------------
class ZohoSyncLog(models.Model):
    run_at = models.DateTimeField(auto_now_add=True)
    ok = models.BooleanField(default=True)
    updated_count = models.IntegerField(default=0)
    issues = models.JSONField(default=list)  # [{invoice_number, issue, detail}]
    error = models.TextField(blank=True, default="")

    class Meta:
        ordering = ["-run_at"]
