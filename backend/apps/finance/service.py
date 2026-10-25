"""Calculs financiers (docs/02-modele-de-donnees.md, règles 19 à 22). Un « mois » est la date du 1er du mois."""
from datetime import date
from decimal import Decimal

from django.db.models import Sum
from django.utils import timezone

from apps.projects.models import Project
from apps.tickets.models import Quote, QuoteInstallment

from .models import DevInstallment, FinanceSettings, ProjectFinance, StaffAllocation

ZERO = Decimal("0.00")


def month_of(d: date) -> date:
    return d.replace(day=1)


def add_months(m: date, n: int) -> date:
    y, mo = divmod(m.year * 12 + m.month - 1 + n, 12)
    return date(y, mo + 1, 1)


def months_between(start: date, end: date) -> list[date]:
    out, m = [], month_of(start)
    while m <= end:
        out.append(m)
        m = add_months(m, 1)
    return out


def parse_month(value: str) -> date:
    """« 2026-09 » ou « 2026-09-15 » → 2026-09-01."""
    parts = [int(x) for x in value.split("-")[:2]]
    return date(parts[0], parts[1], 1)


def finance_of(project: Project) -> ProjectFinance:
    fin, _ = ProjectFinance.objects.get_or_create(project=project)
    return fin


def _accepted_installments(project: Project):
    return QuoteInstallment.objects.filter(quote__ticket__project=project, quote__status=Quote.Status.ACCEPTED)


def start_month(fin: ProjectFinance) -> date | None:
    """Début du projet pour les coûts : première échéance de dev, sinon début de licence."""
    first = fin.installments.order_by("due_on").first()
    return month_of(first.due_on) if first else fin.licence_start


def licence_active(fin: ProjectFinance, month: date) -> bool:
    """Règle 20 : de licence_start jusqu'à licence_end inclus (sans fin : projection illimitée)."""
    return bool(fin.licence_amount and fin.licence_start and fin.licence_start <= month
                and (fin.licence_end is None or month <= fin.licence_end))


def _in_month(qs, month: date):
    return qs.filter(due_on__year=month.year, due_on__month=month.month).aggregate(s=Sum("amount"))["s"] or ZERO


def revenue(project: Project, month: date) -> Decimal:
    """Échéances de dev du mois + licence si active + échéances de devis acceptés du mois.
    Les estimations en jours n'y entrent jamais (règle 22)."""
    fin = finance_of(project)
    total = _in_month(fin.installments.all(), month) + _in_month(_accepted_installments(project), month)
    if licence_active(fin, month):
        total += fin.licence_amount
    return total


def people_cost(project: Project) -> Decimal:
    total = ZERO
    for a in StaffAllocation.objects.filter(project=project).select_related("staff_cost"):
        total += a.staff_cost.monthly_salary * a.percent / 100
    return total.quantize(Decimal("0.01"))


def cost(project: Project, month: date) -> Decimal:
    """Coûts optionnels (règle 19), comptés à partir du début du projet."""
    fin = finance_of(project)
    if fin.cost_mode == ProjectFinance.CostMode.NONE:
        return ZERO
    start = start_month(fin)
    if start is None or month < start:
        return ZERO
    if fin.cost_mode == ProjectFinance.CostMode.MONTHLY:
        return fin.cost_monthly or ZERO
    if fin.cost_mode == ProjectFinance.CostMode.DAYS:
        if (fin.cost_month or start) != month:
            return ZERO
        tjm = fin.cost_tjm or FinanceSettings.load().default_tjm
        return ((fin.cost_days or ZERO) * tjm).quantize(Decimal("0.01"))
    return people_cost(project)


def _paid_split(qs) -> tuple[Decimal, Decimal]:
    paid = qs.filter(is_paid=True).aggregate(s=Sum("amount"))["s"] or ZERO
    left = qs.filter(is_paid=False).aggregate(s=Sum("amount"))["s"] or ZERO
    return paid, left


def summary(project: Project, today: date | None = None) -> dict:
    """Ce que le projet a rapporté depuis le début (vue « Finances » de la maquette)."""
    fin = finance_of(project)
    current = month_of(today or timezone.localdate())
    dev_paid, dev_left = _paid_split(fin.installments.all())
    lic_months = 0
    if fin.licence_amount and fin.licence_start:
        last = min(current, fin.licence_end) if fin.licence_end else current
        lic_months = len(months_between(fin.licence_start, last)) if fin.licence_start <= last else 0
    licence = fin.licence_amount * lic_months
    q_paid, q_left = _paid_split(_accepted_installments(project))
    quotes = Quote.objects.filter(ticket__project=project)
    pending = quotes.filter(status=Quote.Status.SENT).aggregate(s=Sum("amount_ht"))["s"] or ZERO
    start = start_month(fin)
    costs = sum((cost(project, m) for m in months_between(start, current)), ZERO) if start else ZERO
    total = dev_paid + licence + q_paid
    return {
        "dev_paid": dev_paid, "dev_left": dev_left, "dev_total": fin.dev_price,
        "licence": licence, "licence_months": lic_months, "licence_monthly": fin.licence_amount,
        "quotes_paid": q_paid, "quotes_left": q_left,
        "quotes_count": quotes.filter(status=Quote.Status.ACCEPTED).count(),
        "pending_quotes": pending, "total": total, "to_come": dev_left + q_left,
        "has_cost": fin.cost_mode != ProjectFinance.CostMode.NONE, "cost": costs, "margin": total - costs,
    }


def installments_to_come(projects) -> Decimal:
    return DevInstallment.objects.filter(finance__project__in=projects, is_paid=False).aggregate(
        s=Sum("amount"))["s"] or ZERO
