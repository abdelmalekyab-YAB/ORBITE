"""Sprint 5 : exports CSV, PDF de proposition généré, suppression de compte (RGPD), supervision."""
import csv
import io
from datetime import date

from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.projects.models import ProjectAccess
from apps.tickets.models import Comment, Quote, Ticket


def rows(response):
    text = response.content.decode("utf-8-sig")
    return list(csv.reader(io.StringIO(text), delimiter=";"))


# ---------- Exports CSV ----------

def test_ticket_export_respects_client_scope(as_user):
    r = as_user("julie").get("/api/v1/tickets/export.csv")
    assert r.status_code == 200 and r["Content-Type"].startswith("text/csv")
    data = rows(r)
    assert data[0][:3] == ["Référence", "Projet", "Titre"] and "Interne" not in data[0]
    refs = {row[0] for row in data[1:]}
    assert refs and all(ref.split("-")[0] in {"SCV", "CHK"} for ref in refs)
    assert "SCV-4" not in refs  # tâche interne jamais exportée pour un client


def test_ticket_export_digitalia_columns_and_filters(as_user, monkeypatch):
    # The demo data is dated around 29 September 2026: "late" must be computed on that day, not today.
    monkeypatch.setattr(timezone, "localdate", lambda *args, **kwargs: date(2026, 9, 29))
    data = rows(as_user("yanis").get("/api/v1/tickets/export.csv?project=SCV&late=1"))
    assert data[0][-5:] == ["Interne", "Facturation", "Estimation (j)", "Devis HT", "Statut du devis"]
    assert [row[0] for row in data[1:]] == ["SCV-2"]
    scv3 = next(r for r in rows(as_user("yanis").get("/api/v1/tickets/export.csv?project=SCV")) if r[0] == "SCV-3")
    assert scv3[-2:] == ["3600,00", "Envoyée"]


def test_finance_export_is_admin_only(as_user):
    assert as_user("yanis").get("/api/v1/finance/export.csv").status_code == 403
    data = rows(as_user("admin").get("/api/v1/finance/export.csv?from=2026-09&to=2026-10"))
    assert data[0] == ["Ligne", "2026-09", "2026-10", "Total"]
    assert data[-3][0] == "Total recettes" and data[-1][0] == "Marge"
    scv = next(r for r in data if r[0].startswith("SCV"))
    assert scv[2] == "6290,00"  # octobre : échéance 5 400 + licence 890


# ---------- PDF de proposition ----------

def test_pdf_generated_when_none_attached(as_user):
    t = Ticket.objects.get(project__key="RMC", number=9)
    r = as_user("yanis").post(f"/api/v1/tickets/{t.id}/triage",
                              {"decision": "devis", "quote": {"amount_ht": "1200", "parts": 3, "description": "Stats"}},
                              format="json")
    assert r.status_code == 200
    q = Quote.objects.get(ticket=t)
    assert q.pdf.name.endswith("proposition-RMC-9.pdf")
    with q.pdf.open("rb") as f:
        assert f.read(5) == b"%PDF-"
    assert r.data["quote_detail"]["pdf"].endswith(".pdf")


def test_attached_pdf_is_kept_on_resend(as_user):
    t = Ticket.objects.get(project__key="RMC", number=9)
    yanis = as_user("yanis")
    pdf = SimpleUploadedFile("devis-signe.pdf", b"%PDF-1.4 fourni", content_type="application/pdf")
    yanis.post(f"/api/v1/tickets/{t.id}/triage", {"decision": "devis", "quote_amount_ht": "900", "quote_pdf": pdf},
               format="multipart")
    yanis.patch(f"/api/v1/tickets/{t.id}/quote", {"amount_ht": "950"}, format="json")
    yanis.post(f"/api/v1/tickets/{t.id}/quote/send")
    assert "devis-signe" in Quote.objects.get(ticket=t).pdf.name


# ---------- RGPD : suppression (anonymisation) ----------

def test_delete_account_anonymizes_and_keeps_history(as_user):
    admin = as_user("admin")
    marc = User.objects.get(email="marc@rmclub.fr")
    authored = Ticket.objects.filter(author=marc).count()
    assert admin.delete(f"/api/v1/users/{marc.id}").status_code == 204
    marc.refresh_from_db()
    assert marc.email == f"supprime-{marc.id}@orbit.invalid" and marc.get_full_name() == "Utilisateur supprimé"
    assert not marc.is_active and not marc.has_usable_password()
    assert not ProjectAccess.objects.filter(user=marc).exists()
    assert Ticket.objects.filter(author=marc).count() == authored  # historique conservé
    login = APIClient().post("/api/v1/auth/login", {"email": "marc@rmclub.fr", "password": "orbit"}, format="json")
    assert login.status_code == 401
    t = Ticket.objects.filter(author=marc).first()
    assert as_user("yanis").get(f"/api/v1/tickets/{t.id}").data["author"]["name"] == "Utilisateur supprimé"


def test_delete_account_permissions(as_user):
    admin = as_user("admin")
    assert admin.delete(f"/api/v1/users/{admin.user.id}").status_code == 400
    julie = User.objects.get(email="julie@wws.fr")
    assert as_user("yanis").delete(f"/api/v1/users/{julie.id}").status_code == 403
    assert Comment.objects.exists()


# ---------- Supervision ----------

def test_health_reports_components(db, monkeypatch):
    import redis

    monkeypatch.setattr(redis.Redis, "ping", lambda self: True)
    r = APIClient().get("/api/v1/health")
    assert r.status_code == 200 and r.json() == {"status": "ok", "app": "orbit", "database": "ok", "broker": "ok"}

    def down(self):
        raise redis.ConnectionError("down")

    monkeypatch.setattr(redis.Redis, "ping", down)
    r = APIClient().get("/api/v1/health")
    assert r.status_code == 503 and r.json()["broker"] == "down"
