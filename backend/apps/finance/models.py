"""Finances (admin) — docs/02-modele-de-donnees.md, section Finances. Montants en euros HT."""
from decimal import Decimal

from django.conf import settings
from django.db import models


class ProjectFinance(models.Model):
    class CostMode(models.TextChoices):
        NONE = "none", "Ne pas suivre les coûts"
        PEOPLE = "people", "Salaires par personne (affectation %)"
        MONTHLY = "monthly", "Montant mensuel pour ce projet"
        DAYS = "days", "Jours × TJM (coût unique)"

    project = models.OneToOneField("projects.Project", on_delete=models.CASCADE, related_name="finance")
    dev_price = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0"))
    licence_amount = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0"))
    licence_start = models.DateField(null=True, blank=True)  # 1er du mois
    licence_end = models.DateField(null=True, blank=True)
    cost_mode = models.CharField(max_length=10, choices=CostMode.choices, default=CostMode.NONE)
    cost_monthly = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    cost_days = models.DecimalField(max_digits=6, decimal_places=1, null=True, blank=True)
    cost_tjm = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    cost_month = models.DateField(null=True, blank=True)  # mois où le coût unique est comptabilisé
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Finances {self.project.key}"

    def save(self, *args, **kwargs):
        # Les mois se stockent au 1er du mois.
        for field in ("licence_start", "licence_end", "cost_month"):
            value = getattr(self, field)
            if value and value.day != 1:
                setattr(self, field, value.replace(day=1))
        super().save(*args, **kwargs)


class DevInstallment(models.Model):
    finance = models.ForeignKey(ProjectFinance, on_delete=models.CASCADE, related_name="installments")
    due_on = models.DateField()
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    is_paid = models.BooleanField(default=False)
    paid_on = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["due_on", "id"]


class StaffCost(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="staff_cost")
    monthly_salary = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0"))
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


class StaffAllocation(models.Model):
    staff_cost = models.ForeignKey(StaffCost, on_delete=models.CASCADE, related_name="allocations")
    project = models.ForeignKey("projects.Project", on_delete=models.CASCADE, related_name="staff_allocations")
    percent = models.PositiveSmallIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["staff_cost", "project"], name="unique_allocation")]


class FinanceSettings(models.Model):
    """Singleton (pk=1)."""

    # 0 = non défini : l'admin le renseigne dans Finances (aucune valeur inventée).
    default_tjm = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0"))
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    @classmethod
    def load(cls) -> "FinanceSettings":
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj
