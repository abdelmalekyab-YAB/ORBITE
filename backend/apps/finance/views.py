"""API Finances (admin) — docs/05-api.md, section Finances."""
from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.models import User
from apps.projects.models import Project
from apps.tickets import workflow
from apps.tickets.models import Quote, QuoteInstallment, Ticket
from orbit.permissions import IsOrbitAdmin, IsPmOrAdmin

from . import service
from .models import DevInstallment, FinanceSettings, StaffAllocation, StaffCost
from .serializers import (
    DevInstallmentSerializer,
    FinanceSettingsSerializer,
    ProjectFinanceSerializer,
    QuoteInstallmentUpdateSerializer,
    StaffRowSerializer,
)

WINDOW_BEFORE, WINDOW_AFTER = 5, 6  # 12 mois autour d'aujourd'hui, comme la maquette


def _money(d: dict) -> dict:
    return {k: (str(v) if not isinstance(v, bool | int) else v) for k, v in d.items()}


def _window(request):
    current = service.month_of(timezone.localdate())
    start = service.parse_month(request.query_params["from"]) if "from" in request.query_params \
        else service.add_months(current, -WINDOW_BEFORE)
    end = service.parse_month(request.query_params["to"]) if "to" in request.query_params \
        else service.add_months(current, WINDOW_AFTER)
    return current, service.months_between(start, end)


def _mark_paid(obj, data):
    """Poser / retirer `paid_on` en même temps que `is_paid`."""
    if "is_paid" in data and "paid_on" not in data:
        data["paid_on"] = timezone.localdate() if data["is_paid"] else None
    return data


class OverviewView(APIView):
    """GET /finance/overview?from=YYYY-MM&to=YYYY-MM — par mois : recettes par projet, total, coûts, marge."""

    permission_classes = [IsOrbitAdmin]

    def get(self, request):
        current, months = _window(request)
        projects = list(Project.objects.filter(is_archived=False).select_related("client").order_by("key"))
        has_cost = any(service.finance_of(p).cost_mode != "none" for p in projects)
        rows = []
        for m in months:
            by_project = {p.key: service.revenue(p, m) for p in projects}
            total = sum(by_project.values(), service.ZERO)
            costs = sum((service.cost(p, m) for p in projects), service.ZERO)
            rows.append({"month": m.strftime("%Y-%m"), "revenue": {k: str(v) for k, v in by_project.items()},
                         "total": str(total), "cost": str(costs), "margin": str(total - costs)})
        summaries = []
        for p in projects:
            fin = service.finance_of(p)
            summaries.append({"key": p.key, "name": p.name, "client": p.client.name,
                              **_money(service.summary(p, current)),
                              "licence_active": service.licence_active(fin, current)})
        tjm = FinanceSettings.load().default_tjm
        # Règle 22 : aide au chiffrage, jamais comptée en recettes.
        to_quote = Ticket.objects.filter(type__in=["evolution", "feature"], status__is_closed=False,
                                         estimate_days__isnull=False).select_related("project")
        return Response({
            "current": current.strftime("%Y-%m"), "has_cost": has_cost, "months": rows, "projects": summaries,
            "kpis": {
                "licence_monthly": str(sum((service.finance_of(p).licence_amount for p in projects
                                            if service.licence_active(service.finance_of(p), current)), service.ZERO)),
                "dev_to_come": str(service.installments_to_come(projects)),
                "cashed": str(sum((service.summary(p, current)["total"] for p in projects), service.ZERO)),
            },
            "default_tjm": str(tjm),
            "to_quote": [{"id": t.id, "ref": t.ref, "title": t.title, "project": t.project.name,
                          "estimate_days": str(t.estimate_days), "billing": t.billing,
                          "potential": str(((t.estimate_days or 0) * tjm).quantize(service.ZERO))} for t in to_quote],
        })


class ProjectFinanceView(APIView):
    """GET/PUT /finance/projects/{key} — paramètres + synthèse + 12 mois + échéances + devis."""

    permission_classes = [IsOrbitAdmin]

    def _payload(self, project):
        fin = service.finance_of(project)
        current = service.month_of(timezone.localdate())
        months = service.months_between(service.add_months(current, -WINDOW_BEFORE),
                                        service.add_months(current, WINDOW_AFTER))
        quotes = Quote.objects.filter(ticket__project=project).select_related("ticket").prefetch_related("installments")
        return {
            "key": project.key, "name": project.name, "client": project.client.name,
            **ProjectFinanceSerializer(fin).data,
            "summary": _money(service.summary(project, current)),
            "people_cost": str(service.people_cost(project)),
            "months": [{"month": m.strftime("%Y-%m"), "revenue": str(service.revenue(project, m)),
                        "cost": str(service.cost(project, m))} for m in months],
            "installments": DevInstallmentSerializer(fin.installments.all(), many=True).data,
            "quotes": [{"id": q.id, "ticket": {"id": q.ticket_id, "ref": q.ticket.ref, "title": q.ticket.title},
                        "amount_ht": str(q.amount_ht), "status": q.status,
                        "installments": QuoteInstallmentUpdateSerializer(q.installments.all(), many=True).data}
                       for q in quotes],
        }

    def get(self, request, key):
        return Response(self._payload(get_object_or_404(Project, key=key.upper())))

    def put(self, request, key):
        project = get_object_or_404(Project, key=key.upper())
        s = ProjectFinanceSerializer(service.finance_of(project), data=request.data, partial=True)
        s.is_valid(raise_exception=True)
        s.save()
        return Response(self._payload(project))


class InstallmentListView(APIView):
    permission_classes = [IsOrbitAdmin]

    def get(self, request, key):
        fin = service.finance_of(get_object_or_404(Project, key=key.upper()))
        return Response(DevInstallmentSerializer(fin.installments.all(), many=True).data)

    def post(self, request, key):
        fin = service.finance_of(get_object_or_404(Project, key=key.upper()))
        s = DevInstallmentSerializer(data=_mark_paid(None, dict(request.data.items())))
        s.is_valid(raise_exception=True)
        s.save(finance=fin)
        return Response(s.data, status=status.HTTP_201_CREATED)


class InstallmentDetailView(APIView):
    permission_classes = [IsOrbitAdmin]

    def _get(self, key, pk):
        return get_object_or_404(DevInstallment, finance__project__key=key.upper(), pk=pk)

    def patch(self, request, key, pk):
        s = DevInstallmentSerializer(self._get(key, pk), data=_mark_paid(None, dict(request.data.items())),
                                     partial=True)
        s.is_valid(raise_exception=True)
        s.save()
        return Response(s.data)

    def delete(self, request, key, pk):
        self._get(key, pk).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class QuoteInstallmentView(APIView):
    """PATCH /finance/quotes/{quote_id}/installments/{id} — encaissement ou ajustement d'une échéance de devis."""

    permission_classes = [IsOrbitAdmin]

    def patch(self, request, quote_id, pk):
        inst = get_object_or_404(QuoteInstallment.objects.select_related("quote__ticket"), quote_id=quote_id, pk=pk)
        s = QuoteInstallmentUpdateSerializer(inst, data=_mark_paid(None, dict(request.data.items())), partial=True)
        s.is_valid(raise_exception=True)
        s.save()
        workflow.log(inst.quote.ticket, request.user, "quote_installment", to_value=str(inst.amount),
                     message="a mis à jour une échéance de la proposition")
        return Response(s.data)


def _staff_rows():
    projects = list(Project.objects.filter(is_archived=False).order_by("key"))
    rows = []
    for u in User.objects.filter(organization__kind="digitalia", is_active=True).order_by("first_name"):
        sc = StaffCost.objects.filter(user=u).first()
        alloc = {a.project.key: a.percent for a in sc.allocations.select_related("project")} if sc else {}
        total = sum(alloc.values())
        rows.append({"user": u.id, "name": u.get_full_name(), "monthly_salary": str(sc.monthly_salary if sc else 0),
                     "allocations": {p.key: alloc.get(p.key, 0) for p in projects}, "total": total,
                     # Règle 21 : avertissement, jamais blocage.
                     "warning": "Affectations supérieures à 100 %." if total > 100 else None})
    return rows


class StaffView(APIView):
    """GET/PUT /finance/staff — salaires et affectations (mode de coût « par personne »)."""

    permission_classes = [IsOrbitAdmin]

    def get(self, request):
        return Response(_staff_rows())

    @transaction.atomic
    def put(self, request):
        s = StaffRowSerializer(data=request.data, many=True)
        s.is_valid(raise_exception=True)
        projects = {p.key: p for p in Project.objects.all()}
        for row in s.validated_data:
            user = get_object_or_404(User, pk=row["user"], organization__kind="digitalia")
            sc, _ = StaffCost.objects.update_or_create(user=user, defaults={"monthly_salary": row["monthly_salary"]})
            for key, percent in row["allocations"].items():
                if key.upper() not in projects:
                    continue
                StaffAllocation.objects.update_or_create(staff_cost=sc, project=projects[key.upper()],
                                                         defaults={"percent": percent})
        return Response(_staff_rows())


class SettingsView(APIView):
    """GET (pm/admin, pour l'aide au chiffrage du triage) / PUT (admin) /finance/settings."""

    def get_permissions(self):
        return [IsPmOrAdmin()] if self.request.method == "GET" else [IsOrbitAdmin()]

    def get(self, request):
        return Response(FinanceSettingsSerializer(FinanceSettings.load()).data)

    def put(self, request):
        s = FinanceSettingsSerializer(FinanceSettings.load(), data=request.data)
        s.is_valid(raise_exception=True)
        s.save()
        return Response(s.data)


class FinanceExportView(APIView):
    """GET /finance/export.csv?from=YYYY-MM&to=YYYY-MM — recettes mois × projet, coûts et marge (admin)."""

    permission_classes = [IsOrbitAdmin]

    def get(self, request):
        from apps.tickets.export import csv_response

        _current, months = _window(request)
        projects = list(Project.objects.filter(is_archived=False).order_by("key"))
        fr = lambda v: str(v).replace(".", ",")  # noqa: E731
        header = ["Ligne", *[m.strftime("%Y-%m") for m in months], "Total"]
        rows = []
        totals = [service.ZERO] * len(months)
        costs = [sum((service.cost(p, m) for p in projects), service.ZERO) for m in months]
        for p in projects:
            values = [service.revenue(p, m) for m in months]
            totals = [a + b for a, b in zip(totals, values, strict=True)]
            rows.append([f"{p.key} · {p.name}", *map(fr, values), fr(sum(values, service.ZERO))])
        rows.append(["Total recettes", *map(fr, totals), fr(sum(totals, service.ZERO))])
        rows.append(["Coûts", *map(fr, costs), fr(sum(costs, service.ZERO))])
        margins = [a - b for a, b in zip(totals, costs, strict=True)]
        rows.append(["Marge", *map(fr, margins), fr(sum(margins, service.ZERO))])
        return csv_response(f"orbit-finances-{months[0]:%Y%m}-{months[-1]:%Y%m}.csv", header, rows)
