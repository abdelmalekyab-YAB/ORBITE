"""Exports CSV (Sprint 5) : séparateur « ; » et BOM UTF-8 pour une ouverture directe dans Excel (fr)."""
import csv

from django.http import HttpResponse
from django.utils import timezone
from rest_framework.views import APIView

from .scope import visible_tickets
from .views import filter_tickets


def csv_response(filename: str, header: list[str], rows) -> HttpResponse:
    response = HttpResponse(content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    response.write("﻿")
    writer = csv.writer(response, delimiter=";")
    writer.writerow(header)
    writer.writerows(rows)
    return response


def fmt_date(d) -> str:
    return d.strftime("%d/%m/%Y") if d else ""


class TicketExportView(APIView):
    """GET /tickets/export.csv — mêmes filtres et même périmètre que la liste (règles 1-2)."""

    def get(self, request):
        user = request.user
        qs = filter_tickets(visible_tickets(user), request.query_params, user).order_by("project__key", "number")
        header = ["Référence", "Projet", "Titre", "Type", "Étape" if not user.is_digitalia else "Statut",
                  "La balle est chez", "Priorité", "Responsable", "Version", "Date prévue", "En retard",
                  "Déposée le", "Clôturée le"]
        if user.is_digitalia:
            header += ["Interne", "Facturation", "Estimation (j)", "Devis HT", "Statut du devis"]
        ball = {"client": "Client", "digitalia": "Digitalia", "none": "—"}
        rows = []
        for t in qs:
            status = t.status.label if user.is_digitalia else (
                "Clôturée" if t.status.is_closed and not t.status.is_terminal_ok else t.status.client_label)
            row = [t.ref, t.project.name, t.title, t.get_type_display(), status, ball[t.status.ball],
                   t.get_priority_display(), t.assignee.get_full_name() if t.assignee else "",
                   t.milestone.name if t.milestone else "", fmt_date(t.due_on), "oui" if t.is_late else "",
                   fmt_date(timezone.localtime(t.created_at)),
                   fmt_date(timezone.localtime(t.closed_at) if t.closed_at else None)]
            if user.is_digitalia:
                quote = getattr(t, "quote", None) if hasattr(t, "quote") else None
                row += ["oui" if t.is_internal else "", t.get_billing_display() if t.billing else "",
                        str(t.estimate_days or "").replace(".", ","),
                        str(quote.amount_ht).replace(".", ",") if quote else "",
                        quote.get_status_display() if quote else ""]
            rows.append(row)
        return csv_response(f"orbit-demandes-{timezone.localdate():%Y%m%d}.csv", header, rows)
