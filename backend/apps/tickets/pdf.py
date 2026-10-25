"""PDF de proposition commerciale généré quand Digitalia n'en joint pas (Sprint 5)."""
from datetime import timedelta
from io import BytesIO

from django.core.files.base import ContentFile
from django.utils import timezone
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from .models import Quote

VIOLET = colors.HexColor("#7c3aed")


def _euros(value) -> str:
    return f"{value:,.2f} €".replace(",", " ").replace(".", ",")


def render_quote_pdf(quote: Quote) -> bytes:
    from .quotes import INSTALLMENT_GAP_DAYS, SPLITS, split_amount

    ticket = quote.ticket
    styles = getSampleStyleSheet()
    buf = BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=20 * mm, rightMargin=20 * mm, topMargin=18 * mm,
                            bottomMargin=18 * mm, title=f"Proposition {ticket.ref}", author="Digitalia")
    today = timezone.localdate()
    shares = split_amount(quote.amount_ht, quote.parts)
    schedule = [["Échéance", "Part", "Montant HT"]] + [
        [("À la commande" if i == 0 else f"J+{INSTALLMENT_GAP_DAYS * i} après accord"), f"{pct} %", _euros(amount)]
        for i, (pct, amount) in enumerate(zip(SPLITS[quote.parts], shares, strict=True))]
    table = Table(schedule, colWidths=[80 * mm, 30 * mm, 50 * mm])
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), VIOLET), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("ALIGN", (1, 0), (-1, -1), "RIGHT"), ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#d4d0e6")),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6), ("TOPPADDING", (0, 0), (-1, -1), 6)]))
    story = [
        Paragraph("<font color='#7c3aed'><b>DIGITALIA</b></font>", styles["Title"]),
        Paragraph(f"Proposition commerciale — {ticket.ref}", styles["Heading2"]),
        Paragraph(f"Client : <b>{ticket.project.client.name}</b> · Projet : <b>{ticket.project.name}</b>",
                  styles["Normal"]),
        Paragraph(f"Date : {today:%d/%m/%Y} · Valable jusqu'au {(today + timedelta(days=30)):%d/%m/%Y}",
                  styles["Normal"]),
        Spacer(1, 8 * mm),
        Paragraph(f"<b>Objet :</b> {ticket.title}", styles["Normal"]),
        Spacer(1, 3 * mm),
        Paragraph((quote.description or ticket.description or "—").replace("\n", "<br/>"), styles["Normal"]),
        Spacer(1, 8 * mm),
        Paragraph(f"<b>Montant total : {_euros(quote.amount_ht)} HT</b>", styles["Heading3"]),
        table,
        Spacer(1, 8 * mm),
        Paragraph("Le développement démarre dès votre accord, donné directement dans votre espace Orbit.",
                  styles["Italic"]),
    ]
    doc.build(story)
    return buf.getvalue()


def attach_generated_pdf(quote: Quote) -> None:
    quote.pdf.save(f"proposition-{quote.ticket.ref}.pdf", ContentFile(render_quote_pdf(quote)), save=True)
