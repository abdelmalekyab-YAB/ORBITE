"""
API REST du module Finance (Django REST Framework).

Toutes les routes sont réservées au rôle Administration (permission `IsFinanceAdmin`,
à brancher sur le système de rôles d'Orbit — voir permissions.py).
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from django.utils import timezone
from rest_framework import viewsets
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.response import Response

from . import models as M
from . import serializers as S
from .permissions import IsFinanceAdmin
from .services.billing import BillingEngine, add_months, load_snapshot, month_range


def today() -> date:
    return timezone.localdate()


def engine() -> BillingEngine:
    return BillingEngine(load_snapshot(), today())


# ---------------------------------------------------------------------------
# Sérialisation des résultats du moteur (dataclasses → JSON)
# ---------------------------------------------------------------------------
def _p(p):
    return {
        "id": p.id,
        "name": p.name,
        "client_id": p.client_id,
        "billing_type": p.billing_type,
        "status": p.status,
        "monthly_amount": p.monthly_amount,
        "quote_amount": p.quote_amount,
        "start_month": p.start_month,
        "note": p.note,
    }


def _billed(x):
    return {
        "ref": x.ref,
        "project": _p(x.project),
        "month": x.month,
        "amount": x.amount,
        "label": x.label,
        "due_date": x.due_date,
        "payment_status": x.payment_status,
        "paid_on": x.paid_on,
        "pay_state": x.pay_state,
        "has_document": x.has_document,
        "document_name": x.document_name,
    }


def _due(d):
    return {
        "key": d.key,
        "project": _p(d.project),
        "amount": d.amount,
        "label": d.label,
        "overdue_from": d.overdue_from,
    }


@api_view(["GET"])
@permission_classes([IsFinanceAdmin])
def dashboard(request):
    """Tout le tableau de bord en un appel (SPEC §5.1)."""
    e = engine()
    d = e.dashboard()
    cash = d["cash"]
    return Response(
        {
            **{
                k: d[k]
                for k in [
                    "as_of",
                    "month",
                    "month_revenue",
                    "month_fixed",
                    "month_quote",
                    "prev_month_revenue",
                    "ytd",
                    "mrr",
                    "to_bill_total",
                    "billed_this_month_total",
                ]
            },
            "to_bill": [_due(x) for x in d["to_bill"]],
            "billed_this_month": [_billed(x) for x in d["billed_this_month"]],
            "cash": {
                "expected_by_month_end": cash["expected_by_month_end"],
                "total": cash["total"],
                "late_total": cash["late_total"],
                "this_month_total": cash["this_month_total"],
                "no_due_total": cash["no_due_total"],
                "later_total": cash["later_total"],
                "late": [_billed(x) for x in cash["late"]],
                "this_month": [_billed(x) for x in cash["this_month"]],
                "no_due": [_billed(x) for x in cash["no_due"]],
                "later_by_month": {m: [_billed(x) for x in v] for m, v in cash["later_by_month"].items()},
            },
            "remaining": [{**r, "project": _p(r["project"])} for r in d["remaining"]],
            "proposals": [{**r, "project": _p(r["project"])} for r in d["proposals"]],
            "ranking_12": [{**r, "project": _p(r["project"])} for r in d["ranking_12"]],
            "chart_12": d["chart_12"],
            "clients": [{"id": c.id, "name": c.name} for c in e.s.clients],
        }
    )


@api_view(["GET"])
@permission_classes([IsFinanceAdmin])
def month_view(request, month: str):
    """Saisie du mois (SPEC §5.2) : une ligne par projet actif ou facturé ce mois."""
    e = engine()
    rows, total, to_bill = [], Decimal(0), Decimal(0)
    for p in e.s.projects:
        inv = [i for i in e.invoices_of(p) if i.service_month == month]
        if not ((p.active_in(month) and not p.is_proposal) or inv):
            continue
        row = {"project": _p(p), "fixed": None, "invoices": [], "total": Decimal(0)}
        if p.is_fixed and not p.is_proposal and p.active_in(month):
            o = e.occurrence(p, month)
            v = e.fixed_value(p, month)
            billed = e.fixed_billed(p, month)
            future = month > e.now
            if not future and billed:
                row["total"] += v
            if month == e.now and not billed:
                to_bill += v
            row["fixed"] = {
                "amount": v,
                "adjusted": bool(o and o.override_amount is not None),
                "billed": billed,
                "is_current": month == e.now,
                "future": future,
                "pay_state": e._pay_state(o.payment_status, o.due_date) if (o and billed) else None,
                "due_date": o.due_date if o else None,
                "paid_on": o.paid_on if o else None,
                "has_document": bool(o and o.has_document),
                "document_name": o.document_name if o else "",
            }
        for i in inv:
            pending = e.is_pending(i)
            if not pending:
                row["total"] += Decimal(i.amount)
            elif month <= e.now:
                to_bill += Decimal(i.amount)
            row["invoices"].append(
                {
                    "id": i.id,
                    "amount": i.amount,
                    "label": i.label,
                    "kind": i.kind,
                    "status": i.status,
                    "pending": pending,
                    "pay_state": None if pending else e._pay_state(i.payment_status, i.due_date),
                    "due_date": i.due_date,
                    "paid_on": i.paid_on,
                    "has_document": i.has_document,
                    "document_name": i.document_name,
                }
            )
        total += row["total"]
        rows.append(row)
    rows.sort(
        key=lambda r: (
            e.client(r["project"]["client_id"]).name if e.client(r["project"]["client_id"]) else "",
            r["project"]["name"],
        )
    )
    return Response({"month": month, "rows": rows, "total": total, "to_bill": to_bill, "current_month": e.now})


@api_view(["GET"])
@permission_classes([IsFinanceAdmin])
def upcoming(request):
    """À venir (SPEC §5.3)."""
    horizon = int(request.query_params.get("horizon", 6))
    e = engine()
    months = month_range(e.now, add_months(e.now, horizon))
    forecast = []
    for m in months:
        fixed = sum((e.fixed_to_bill(p, m) for p in e.s.projects), Decimal(0))
        planned = sum(
            (
                Decimal(i.amount)
                for i in e.s.invoices
                if e.is_pending(i) and (i.service_month <= e.now if m == e.now else i.service_month == m)
            ),
            Decimal(0),
        )
        forecast.append({"month": m, "fixed": fixed, "planned": planned})
    planned_list = [i for i in e.s.invoices if e.is_pending(i)]
    planned_list.sort(key=lambda i: i.service_month)
    return Response(
        {
            "remaining": [{**r, "project": _p(r["project"])} for r in e.remaining_to_bill()],
            "proposals": [{**r, "project": _p(r["project"])} for r in e.proposals()],
            "forecast": forecast,
            "planned": [
                {
                    "id": i.id,
                    "project": _p(e.project(i.project_id)),
                    "service_month": i.service_month,
                    "amount": i.amount,
                    "label": i.label,
                    "due_now": e.due_now(i),
                }
                for i in planned_list
            ],
        }
    )


@api_view(["GET"])
@permission_classes([IsFinanceAdmin])
def recap(request):
    """Récap mensuel (SPEC §5.4)."""
    period = request.query_params.get("period", "all")
    e = engine()
    start = {"year": e.now[:4] + "-01", "12": add_months(e.now, -11)}.get(period, e.first_month())
    mx = e.client_month_matrix(start, e.now)
    detail = []
    for m in mx["months"]:
        clients = []
        for c in e.s.clients:
            projs = []
            for p in e.s.projects:
                if p.client_id != c.id:
                    continue
                r = e.project_month(p, m)
                if not r.revenue:
                    continue
                lines = ([f"Montant fixe {r.fixed}"] if r.fixed else []) + [
                    f"{i.label or 'Facture'} · {i.amount}"
                    for i in e.invoices_of(p)
                    if i.service_month == m and e.is_billed(i)
                ]
                projs.append({"project": _p(p), "revenue": r.revenue, "lines": lines})
            if projs:
                clients.append(
                    {
                        "client": {"id": c.id, "name": c.name},
                        "revenue": sum((x["revenue"] for x in projs), Decimal(0)),
                        "projects": projs,
                    }
                )
        detail.append({"month": m, "revenue": e.month_totals(m).revenue, "clients": clients})
    return Response(
        {
            "months": mx["months"],
            "matrix": mx["matrix"],
            "detail": detail,
            "clients": [{"id": c.id, "name": c.name} for c in e.s.clients],
        }
    )


# ---------------------------------------------------------------------------
# CRUD
# ---------------------------------------------------------------------------
class BillingProfileViewSet(viewsets.ModelViewSet):
    queryset = M.BillingProfile.objects.select_related("project", "project__client").prefetch_related("documents")
    serializer_class = S.BillingProfileSerializer
    permission_classes = [IsFinanceAdmin]
    parser_classes = [JSONParser, MultiPartParser, FormParser]

    @action(detail=True, methods=["post"])
    def documents(self, request, pk=None):
        bp = self.get_object()
        f = request.FILES["file"]
        M.ProjectDocument.objects.create(profile=bp, kind=request.data.get("kind", ""), file=f, original_name=f.name)
        return Response(self.get_serializer(bp).data, status=201)

    @action(detail=True, methods=["get"])
    def sheet(self, request, pk=None):
        """Fiche projet (SPEC §5.8) : historique mois par mois."""
        bp = self.get_object()
        e = engine()
        p = e.project(str(bp.project_id))
        inv = e.invoices_of(p)
        start, end = e.first_billed_month(p), e.now
        for i in inv:
            end = max(end, i.service_month)
        if p.is_fixed and p.end_month and p.end_month > end:
            end = min(p.end_month, add_months(e.now, 12))
        rows = []
        for m in month_range(start, end):
            fixed = e.fixed_value(p, m)
            es = [i for i in inv if i.service_month == m]
            tot = fixed + sum((Decimal(i.amount) for i in es), Decimal(0))
            if not (tot or es):
                continue
            rows.append(
                {
                    "month": m,
                    "fixed": fixed,
                    "fixed_billed": e.fixed_billed(p, m) if fixed else None,
                    "to_bill": (m == e.now and fixed > 0 and not e.fixed_billed(p, m))
                    or any(e.is_pending(i) and m <= e.now for i in es),
                    "future": m > e.now,
                    "total": tot,
                    "invoices": [
                        {
                            "id": i.id,
                            "amount": i.amount,
                            "label": i.label,
                            "kind": i.kind,
                            "pending": e.is_pending(i),
                            "pay_state": None if e.is_pending(i) else e._pay_state(i.payment_status, i.due_date),
                            "has_document": i.has_document,
                        }
                        for i in es
                    ],
                }
            )
        rows.reverse()
        billed = e.billed_to_date(p)
        cost = sum((e.project_month(p, m).cost for m in month_range(p.start_month, e.now)), Decimal(0))
        rem = next((r["remaining"] for r in e.remaining_to_bill() if r["project"].id == p.id), None)
        return Response(
            {
                "profile": self.get_serializer(bp).data,
                "first_billed_month": start,
                "billed": billed,
                "remaining": rem,
                "planned": e.planned_of(p),
                "cost": cost,
                "margin": billed - cost if cost else None,
                "rows": rows,
            }
        )


class InvoiceViewSet(viewsets.ModelViewSet):
    queryset = M.Invoice.objects.select_related("project")
    serializer_class = S.InvoiceSerializer
    permission_classes = [IsFinanceAdmin]
    parser_classes = [JSONParser, MultiPartParser, FormParser]
    filterset_fields = ["project", "service_month", "status", "kind"]

    @action(detail=True, methods=["post"])
    def mark_issued(self, request, pk=None):
        """Facture prévue dont le mois est atteint → émise (SPEC §6)."""
        inv = self.get_object()
        now = today().strftime("%Y-%m")
        inv.status = M.Invoice.ISSUED
        if inv.service_month < now:
            inv.service_month = now
        inv.issued_on = inv.issued_on or today()
        inv.save()
        return Response(self.get_serializer(inv).data)

    @action(detail=True, methods=["post"])
    def mark_planned(self, request, pk=None):
        inv = self.get_object()
        inv.status = M.Invoice.PLANNED
        inv.save()
        return Response(self.get_serializer(inv).data)

    @action(detail=True, methods=["post"])
    def payment(self, request, pk=None):
        inv = self.get_object()
        s = S.PaymentUpdateSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        for k, v in s.validated_data.items():
            setattr(inv, k, v)
        if inv.payment_status != M.Invoice.PAID:
            inv.paid_on = None
        inv.save()
        return Response(self.get_serializer(inv).data)

    @action(detail=True, methods=["post"])
    def document(self, request, pk=None):
        inv = self.get_object()
        f = request.FILES["file"]
        inv.document = f
        inv.document_name = f.name
        inv.save()
        return Response(self.get_serializer(inv).data)

    @action(detail=False, methods=["post"])
    def forecast_7421(self, request):
        """Met à jour (jamais ne duplique) la ligne « CA prévu 74+21 » du mois (SPEC §7.3)."""
        project_id, month, amount = (
            request.data["project"],
            request.data["service_month"],
            Decimal(str(request.data["amount"])),
        )
        label = request.data.get("label") or f"CA prévu 74 + 21 (tableau de bord suivi) · mis à jour le {today():%d/%m}"
        inv, created = M.Invoice.objects.get_or_create(
            project_id=project_id,
            service_month=month,
            kind=M.Invoice.FORECAST_7421,
            defaults={"amount": amount, "label": label, "status": M.Invoice.PLANNED},
        )
        if not created:
            if inv.status == M.Invoice.ISSUED:
                return Response({"detail": "La ligne du mois est déjà émise : confirmation requise."}, status=409)
            inv.amount, inv.label = amount, label
            inv.save()
        return Response(self.get_serializer(inv).data, status=201 if created else 200)


class FixedOccurrenceViewSet(viewsets.ModelViewSet):
    """Ajuster / marquer facturé / payer / joindre pour un (projet, mois) fixe."""

    queryset = M.FixedOccurrence.objects.all()
    serializer_class = S.FixedOccurrenceSerializer
    permission_classes = [IsFinanceAdmin]
    parser_classes = [JSONParser, MultiPartParser, FormParser]

    def _get(self, project_id, month):
        return M.FixedOccurrence.objects.get_or_create(project_id=project_id, month=month)[0]

    @action(detail=False, methods=["post"])
    def adjust(self, request):
        o = self._get(request.data["project"], request.data["month"])
        o.override_amount = None if request.data.get("reset") else Decimal(str(request.data["amount"]))
        o.save()
        return Response(self.get_serializer(o).data)

    @action(detail=False, methods=["post"])
    def mark(self, request):
        """Marquer facturé (ou annuler) — uniquement pour le mois en cours (R5)."""
        if request.data["month"] != today().strftime("%Y-%m"):
            return Response({"detail": "Seul le mois en cours peut être marqué."}, status=400)
        o = self._get(request.data["project"], request.data["month"])
        o.billed_marked = bool(request.data.get("billed", True))
        o.save()
        return Response(self.get_serializer(o).data)

    @action(detail=False, methods=["post"])
    def payment(self, request):
        o = self._get(request.data["project"], request.data["month"])
        s = S.PaymentUpdateSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        for k, v in s.validated_data.items():
            setattr(o, k, v)
        if o.payment_status != M.FixedOccurrence.PAID:
            o.paid_on = None
        o.save()
        return Response(self.get_serializer(o).data)

    @action(detail=False, methods=["post"])
    def document(self, request):
        o = self._get(request.data["project"], request.data["month"])
        f = request.FILES["file"]
        o.document = f
        o.document_name = f.name
        o.save()
        return Response(self.get_serializer(o).data)


class ExpenseViewSet(viewsets.ModelViewSet):
    queryset = M.Expense.objects.select_related("project")
    serializer_class = S.ExpenseSerializer
    permission_classes = [IsFinanceAdmin]
    parser_classes = [JSONParser, MultiPartParser, FormParser]

    def get_queryset(self):
        qs = super().get_queryset()
        m = self.request.query_params.get("month")
        return qs.filter(date__startswith=m) if m else qs

    @action(detail=True, methods=["post"])
    def receipt(self, request, pk=None):
        x = self.get_object()
        f = request.FILES["file"]
        x.receipt = f
        x.receipt_name = f.name
        x.save()
        return Response(self.get_serializer(x).data)


# ---------------------------------------------------------------------------
# Exports (SPEC §8) — génération côté serveur
# ---------------------------------------------------------------------------
@api_view(["GET"])
@permission_classes([IsFinanceAdmin])
def export_accounting(request):
    """?from=YYYY-MM&to=YYYY-MM&client=<id>&expenses=1&kind=xlsx|zip  (ne pas utiliser `format`, réservé par DRF)"""
    from .services.exports import accounting_package

    fmt = request.query_params.get("kind", "zip")
    content, filename, ctype = accounting_package(
        engine(),
        request.query_params.get("from"),
        request.query_params.get("to"),
        request.query_params.get("client"),
        request.query_params.get("expenses", "1") == "1",
        fmt,
    )
    from django.http import HttpResponse

    resp = HttpResponse(content, content_type=ctype)
    resp["Content-Disposition"] = f'attachment; filename="{filename}"'
    return resp


@api_view(["GET"])
@permission_classes([IsFinanceAdmin])
def export_ceo_pdf(request):
    from django.http import HttpResponse

    from .services.exports import ceo_report_pdf

    e = engine()
    pdf = ceo_report_pdf(e)
    resp = HttpResponse(pdf, content_type="application/pdf")
    resp["Content-Disposition"] = f'attachment; filename="DIGITALIA_rapport_facturation_{e.now}.pdf"'
    return resp


@api_view(["POST"])
@permission_classes([IsFinanceAdmin])
def zoho_sync(request):
    """Synchronisation LECTURE SEULE des statuts de paiement (SPEC §9)."""
    from .services.zoho import sync_payment_statuses

    log = sync_payment_statuses()
    return Response({"ok": log.ok, "updated": log.updated_count, "issues": log.issues, "error": log.error})


@api_view(["GET"])
@permission_classes([IsFinanceAdmin])
def orbit_projects(request):
    """Projets Orbit (non archivés) pour rattacher un profil de facturation."""
    from apps.projects.models import Project

    qs = Project.objects.filter(is_archived=False).select_related("client").order_by("client__name", "name")
    return Response(
        [{"id": p.pk, "name": p.name, "client_id": str(p.client_id), "client_name": p.client.name} for p in qs]
    )
