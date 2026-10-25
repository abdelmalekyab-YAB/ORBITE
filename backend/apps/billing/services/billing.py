"""
Orbit · Finance — moteur de calcul (SPEC §4, règles R1 → R21).

Port fidèle de la logique JavaScript de la plateforme actuelle. Le moteur travaille
sur un *snapshot* en mémoire (dataclasses) chargé une fois par requête : il ne fait
aucune requête ORM pendant les calculs, ce qui garde les écrans rapides et rend la
logique testable sans base de données (voir tests/test_reference.py).

Usage :
    snap = load_snapshot()                     # depuis l'ORM
    eng  = BillingEngine(snap, today=date.today())
    eng.month_totals("2026-10")
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal

D0 = Decimal("0")


# ---------------------------------------------------------------------------
# Utilitaires mois
# ---------------------------------------------------------------------------
def add_months(ym: str, n: int) -> str:
    y, m = int(ym[:4]), int(ym[5:7])
    m += n
    y += (m - 1) // 12
    m = (m - 1) % 12 + 1
    return f"{y:04d}-{m:02d}"


def month_range(start: str, end: str, cap: int = 600) -> list[str]:
    out, m = [], start
    while m <= end and len(out) < cap:
        out.append(m)
        m = add_months(m, 1)
    return out


def ym(d: date) -> str:
    return d.strftime("%Y-%m")


# ---------------------------------------------------------------------------
# Snapshot (indépendant de l'ORM)
# ---------------------------------------------------------------------------
@dataclass
class Client:
    id: str
    name: str


@dataclass
class Project:
    id: str
    client_id: str
    name: str
    billing_type: str  # "fixed" | "quote"
    monthly_amount: Decimal = D0
    quote_amount: Decimal | None = None
    cost: Decimal = D0
    start_month: str = ""
    end_month: str = ""
    status: str = "validated"  # "validated" | "proposal"
    note: str = ""

    @property
    def is_fixed(self):
        return self.billing_type == "fixed"

    @property
    def is_proposal(self):
        return self.status == "proposal"

    def active_in(self, m: str) -> bool:  # R1
        return self.start_month <= m and (not self.end_month or m <= self.end_month)


@dataclass
class Invoice:
    id: str
    project_id: str
    service_month: str
    amount: Decimal
    label: str = ""
    kind: str = "invoice"  # invoice | deposit | forecast_7421
    status: str = "issued"  # issued | planned
    due_date: date | None = None
    payment_status: str = "pending"
    paid_on: date | None = None
    has_document: bool = False
    document_name: str = ""

    @property
    def is_planned(self):
        return self.status == "planned"


@dataclass
class FixedOccurrence:
    project_id: str
    month: str
    override_amount: Decimal | None = None
    billed_marked: bool = False
    due_date: date | None = None
    payment_status: str = "pending"
    paid_on: date | None = None
    has_document: bool = False
    document_name: str = ""


@dataclass
class Expense:
    id: str
    date: date
    supplier: str
    category: str
    label: str
    project_id: str | None
    amount_ht: Decimal
    vat: Decimal = D0
    has_receipt: bool = False
    receipt_name: str = ""

    @property
    def month(self):
        return ym(self.date)


@dataclass
class Snapshot:
    clients: list[Client] = field(default_factory=list)
    projects: list[Project] = field(default_factory=list)
    invoices: list[Invoice] = field(default_factory=list)
    occurrences: list[FixedOccurrence] = field(default_factory=list)
    expenses: list[Expense] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Résultats typés
# ---------------------------------------------------------------------------
@dataclass
class MonthTotals:
    revenue: Decimal = D0
    fixed: Decimal = D0
    quote: Decimal = D0
    cost: Decimal = D0


@dataclass
class BilledItem:
    """Une facture émise (ou une occurrence fixe facturée) — base des encaissements."""

    ref: str  # "inv:<id>" | "fix:<project>|<month>"
    project: Project
    month: str
    amount: Decimal
    label: str
    due_date: date | None
    payment_status: str
    paid_on: date | None
    pay_state: str  # paid | late | due | wait  (R15)
    has_document: bool = False
    document_name: str = ""


@dataclass
class DueItem:
    """Quelque chose à facturer ce mois (R11)."""

    key: str  # "fix:<project>" | "inv:<id>"
    project: Project
    amount: Decimal
    label: str
    overdue_from: str | None = None  # mois d'origine si prévue en retard


# ---------------------------------------------------------------------------
# Moteur
# ---------------------------------------------------------------------------
class BillingEngine:
    def __init__(self, snap: Snapshot, today: date):
        self.s = snap
        self.today = today
        self.now = ym(today)
        self._projects = {p.id: p for p in snap.projects}
        self._clients = {c.id: c for c in snap.clients}
        self._occ = {(o.project_id, o.month): o for o in snap.occurrences}
        self._inv_by_project: dict[str, list[Invoice]] = {}
        for i in snap.invoices:
            self._inv_by_project.setdefault(i.project_id, []).append(i)

    # ---- accès ----
    def project(self, pid: str) -> Project | None:
        return self._projects.get(pid)

    def client(self, cid: str) -> Client | None:
        return self._clients.get(cid)

    def invoices_of(self, p: Project) -> list[Invoice]:
        return self._inv_by_project.get(p.id, [])

    def occurrence(self, p: Project, m: str) -> FixedOccurrence | None:
        return self._occ.get((p.id, m))

    # ---- R2 / R3 ----
    def fixed_billed(self, p: Project, m: str) -> bool:
        if m < self.now:
            return True
        if m == self.now:
            o = self.occurrence(p, m)
            return bool(o and o.billed_marked)
        return False

    def fixed_value(self, p: Project, m: str) -> Decimal:
        if not (p.is_fixed and not p.is_proposal and p.active_in(m)):
            return D0
        o = self.occurrence(p, m)
        if o and o.override_amount is not None:
            return Decimal(o.override_amount)
        return Decimal(p.monthly_amount or 0)

    def fixed_to_bill(self, p: Project, m: str) -> Decimal:
        return D0 if self.fixed_billed(p, m) else self.fixed_value(p, m)

    # ---- R6 ----
    def is_billed(self, i: Invoice) -> bool:
        return (not i.is_planned) and i.service_month <= self.now

    def is_pending(self, i: Invoice) -> bool:
        return not self.is_billed(i)

    def due_now(self, i: Invoice) -> bool:
        return self.is_pending(i) and i.service_month <= self.now

    # ---- R7 / R9 ----
    def project_month(self, p: Project, m: str) -> MonthTotals:
        t = MonthTotals()
        if p.is_fixed and not p.is_proposal and p.active_in(m) and self.fixed_billed(p, m):
            t.fixed = self.fixed_value(p, m)
            t.cost += Decimal(p.cost or 0)
        if (not p.is_fixed) and m == p.start_month and m <= self.now:
            t.cost += Decimal(p.cost or 0)
        for i in self.invoices_of(p):
            if i.service_month == m and self.is_billed(i):
                t.quote += Decimal(i.amount)
        for x in self.s.expenses:
            if x.project_id == p.id and x.month == m:
                t.cost += Decimal(x.amount_ht)
        t.revenue = t.fixed + t.quote
        return t

    # ---- R8 ----
    def month_totals(self, m: str) -> MonthTotals:
        t = MonthTotals()
        for p in self.s.projects:
            r = self.project_month(p, m)
            t.revenue += r.revenue
            t.fixed += r.fixed
            t.quote += r.quote
            t.cost += r.cost
        for x in self.s.expenses:
            if x.project_id is None and x.month == m:
                t.cost += Decimal(x.amount_ht)
        return t

    def first_month(self) -> str:
        f = self.now
        for p in self.s.projects:
            if p.start_month and p.start_month < f:
                f = p.start_month
        for i in self.s.invoices:
            if i.service_month < f:
                f = i.service_month
        return f

    def first_billed_month(self, p: Project) -> str:
        f = p.start_month
        for i in self.invoices_of(p):
            if i.service_month < f:
                f = i.service_month
        return f

    # ---- R10 ----
    def billed_to_date(self, p: Project) -> Decimal:
        total = sum((Decimal(i.amount) for i in self.invoices_of(p) if self.is_billed(i)), D0)
        if p.is_fixed:
            for m in month_range(p.start_month, self.now):
                if self.fixed_billed(p, m):
                    total += self.fixed_value(p, m)
        return total

    def planned_of(self, p: Project) -> Decimal:
        return sum((Decimal(i.amount) for i in self.invoices_of(p) if self.is_pending(i)), D0)

    # ---- R11 ----
    def due_items(self) -> list[DueItem]:
        out: list[DueItem] = []
        for p in self.s.projects:
            v = self.fixed_to_bill(p, self.now)
            if v:
                out.append(DueItem(f"fix:{p.id}", p, v, "Montant fixe du mois"))
        for i in self.s.invoices:
            if self.due_now(i):
                p = self.project(i.project_id)
                if p:
                    out.append(
                        DueItem(
                            f"inv:{i.id}",
                            p,
                            Decimal(i.amount),
                            i.label or "Facture prévue",
                            overdue_from=i.service_month if i.service_month < self.now else None,
                        )
                    )
        out.sort(key=lambda x: -x.amount)
        return out

    # ---- R12 + base des encaissements ----
    def billed_items(self) -> list[BilledItem]:
        out: list[BilledItem] = []
        for p in self.s.projects:
            if p.is_fixed and not p.is_proposal:
                for m in month_range(p.start_month, self.now):
                    if p.active_in(m) and self.fixed_billed(p, m):
                        v = self.fixed_value(p, m)
                        if v:
                            o = self.occurrence(p, m)
                            out.append(
                                BilledItem(
                                    ref=f"fix:{p.id}|{m}",
                                    project=p,
                                    month=m,
                                    amount=v,
                                    label=f"Montant fixe {m}",
                                    due_date=o.due_date if o else None,
                                    payment_status=o.payment_status if o else "pending",
                                    paid_on=o.paid_on if o else None,
                                    pay_state=self._pay_state(
                                        o.payment_status if o else "pending", o.due_date if o else None
                                    ),
                                    has_document=bool(o and o.has_document),
                                    document_name=o.document_name if o else "",
                                )
                            )
        for i in self.s.invoices:
            if self.is_billed(i):
                p = self.project(i.project_id)
                if p:
                    out.append(
                        BilledItem(
                            ref=f"inv:{i.id}",
                            project=p,
                            month=i.service_month,
                            amount=Decimal(i.amount),
                            label=i.label or "Facture",
                            due_date=i.due_date,
                            payment_status=i.payment_status,
                            paid_on=i.paid_on,
                            pay_state=self._pay_state(i.payment_status, i.due_date),
                            has_document=i.has_document,
                            document_name=i.document_name,
                        )
                    )
        return out

    # ---- R15 ----
    def _pay_state(self, status: str, due: date | None) -> str:
        if status == "paid":
            return "paid"
        if status == "late" or (due and due < self.today):
            return "late"
        return "due" if due else "wait"

    # ---- R16 ----
    def cash_summary(self) -> dict:
        items = [x for x in self.billed_items() if x.pay_state != "paid"]
        late = [x for x in items if x.pay_state == "late"]
        this_m = [x for x in items if x.pay_state != "late" and x.due_date and ym(x.due_date) == self.now]
        no_due = [x for x in items if x.pay_state != "late" and not x.due_date]
        later = [x for x in items if x.pay_state != "late" and x.due_date and ym(x.due_date) > self.now]
        by_month: dict[str, list[BilledItem]] = {}
        for x in later:
            by_month.setdefault(ym(x.due_date), []).append(x)

        def s(a):
            return sum((x.amount for x in a), D0)

        return {
            "late": late,
            "this_month": this_m,
            "no_due": no_due,
            "later_by_month": dict(sorted(by_month.items())),
            "late_total": s(late),
            "this_month_total": s(this_m),
            "no_due_total": s(no_due),
            "later_total": s(later),
            "expected_by_month_end": s(late) + s(this_m),
            "total": s(items),
        }

    # ---- R13 ----
    def remaining_to_bill(self) -> list[dict]:
        rows = []
        for p in self.s.projects:
            if p.is_proposal:
                continue
            billed, planned = self.billed_to_date(p), self.planned_of(p)
            if (not p.is_fixed) and p.quote_amount:
                rem = max(Decimal(p.quote_amount) - billed, D0)
                if rem > 0:
                    rows.append(
                        {
                            "project": p,
                            "remaining": rem,
                            "billed": billed,
                            "total": Decimal(p.quote_amount),
                            "planned": planned,
                            "unplanned": max(rem - planned, D0),
                            "kind": "quote",
                        }
                    )
            elif p.is_fixed and p.end_month and p.end_month >= self.now:
                rem = sum((self.fixed_to_bill(p, m) for m in month_range(self.now, p.end_month)), D0)
                if rem > 0:
                    rows.append(
                        {
                            "project": p,
                            "remaining": rem,
                            "billed": billed,
                            "total": billed + rem,
                            "planned": D0,
                            "unplanned": D0,
                            "kind": "fixed",
                        }
                    )
        rows.sort(key=lambda r: -r["remaining"])
        return rows

    # ---- R14 ----
    def proposals(self) -> list[dict]:
        out = []
        for p in self.s.projects:
            if not p.is_proposal:
                continue
            value = Decimal(p.monthly_amount or 0) * 12 if p.is_fixed else Decimal(p.quote_amount or 0)
            waiting = max(0, len(month_range(p.start_month, self.now)) - 1)
            out.append({"project": p, "value": value, "waiting_months": waiting})
        out.sort(key=lambda r: r["project"].start_month)
        return out

    # ---- R17 / R18 ----
    def mrr(self) -> Decimal:
        return sum(
            (
                Decimal(p.monthly_amount or 0)
                for p in self.s.projects
                if p.is_fixed and not p.is_proposal and p.active_in(self.now)
            ),
            D0,
        )

    def year_to_date(self) -> Decimal:
        return sum((self.month_totals(m).revenue for m in month_range(self.now[:4] + "-01", self.now)), D0)

    # ---- R19 ----
    def ranking(self, period: str = "12") -> list[dict]:
        if period == "12":
            months = month_range(add_months(self.now, -11), self.now)
        elif period == "year":
            months = month_range(self.now[:4] + "-01", self.now)
        else:
            months = month_range(self.first_month(), self.now)
        rows = []
        for p in self.s.projects:
            rev = cost = D0
            for m in months:
                r = self.project_month(p, m)
                rev += r.revenue
                cost += r.cost
            if rev or cost:
                rows.append({"project": p, "revenue": rev, "cost": cost, "margin": rev - cost})
        any_cost = any(r["cost"] for r in rows)
        rows.sort(key=lambda r: -(r["margin"] if any_cost else r["revenue"]))
        return rows

    # ---- Récap par client / mois ----
    def client_month_matrix(self, start: str, end: str) -> dict:
        months = month_range(start, end)
        matrix = {}
        for c in self.s.clients:
            row = {}
            for m in months:
                row[m] = sum((self.project_month(p, m).revenue for p in self.s.projects if p.client_id == c.id), D0)
            matrix[c.id] = row
        return {"months": months, "matrix": matrix}

    # ---- Dashboard complet (ce que l'API /dashboard renvoie) ----
    def dashboard(self) -> dict:
        t = self.month_totals(self.now)
        prev = self.month_totals(add_months(self.now, -1)).revenue
        due = self.due_items()
        billed_m = [x for x in self.billed_items() if x.month == self.now]
        return {
            "as_of": self.today.isoformat(),
            "month": self.now,
            "month_revenue": t.revenue,
            "month_fixed": t.fixed,
            "month_quote": t.quote,
            "prev_month_revenue": prev,
            "ytd": self.year_to_date(),
            "mrr": self.mrr(),
            "to_bill_total": sum((d.amount for d in due), D0),
            "to_bill": due,
            "billed_this_month_total": sum((x.amount for x in billed_m), D0),
            "billed_this_month": billed_m,
            "cash": self.cash_summary(),
            "remaining": self.remaining_to_bill(),
            "proposals": self.proposals(),
            "ranking_12": self.ranking("12"),
            "chart_12": [
                {"month": m, **self._client_split(m)} for m in month_range(add_months(self.now, -11), self.now)
            ],
        }

    def _client_split(self, m: str) -> dict:
        return {
            c.id: sum((self.project_month(p, m).revenue for p in self.s.projects if p.client_id == c.id), D0)
            for c in self.s.clients
        }


# ---------------------------------------------------------------------------
# Chargement depuis l'ORM
# ---------------------------------------------------------------------------
def load_snapshot() -> Snapshot:
    from apps.billing import models as M

    snap = Snapshot()
    profiles = M.BillingProfile.objects.select_related("project", "project__client")
    for bp in profiles:
        snap.projects.append(
            Project(
                id=str(bp.project_id),
                client_id=str(bp.project.client_id),
                name=bp.project.name,
                billing_type=bp.billing_type,
                monthly_amount=bp.monthly_amount,
                quote_amount=bp.quote_amount,
                cost=bp.cost,
                start_month=bp.start_month,
                end_month=bp.end_month or "",
                status=bp.status,
                note=bp.note,
            )
        )
    {p.client_id for p in snap.projects}
    ClientModel = M.BillingProfile._meta.get_field("project").related_model._meta.get_field("client").related_model
    for c in ClientModel.objects.all():
        snap.clients.append(Client(id=str(c.pk), name=c.name))
    for i in M.Invoice.objects.all():
        snap.invoices.append(
            Invoice(
                id=str(i.pk),
                project_id=str(i.project_id),
                service_month=i.service_month,
                amount=i.amount,
                label=i.label,
                kind=i.kind,
                status=i.status,
                due_date=i.due_date,
                payment_status=i.payment_status,
                paid_on=i.paid_on,
                has_document=bool(i.document),
                document_name=i.document_name,
            )
        )
    for o in M.FixedOccurrence.objects.all():
        snap.occurrences.append(
            FixedOccurrence(
                project_id=str(o.project_id),
                month=o.month,
                override_amount=o.override_amount,
                billed_marked=o.billed_marked,
                due_date=o.due_date,
                payment_status=o.payment_status,
                paid_on=o.paid_on,
                has_document=bool(o.document),
                document_name=o.document_name,
            )
        )
    for x in M.Expense.objects.all():
        snap.expenses.append(
            Expense(
                id=str(x.pk),
                date=x.date,
                supplier=x.supplier,
                category=x.category,
                label=x.label,
                project_id=str(x.project_id) if x.project_id else None,
                amount_ht=x.amount_ht,
                vat=x.vat,
                has_receipt=bool(x.receipt),
                receipt_name=x.receipt_name,
            )
        )
    return snap


def snapshot_from_export(data: dict) -> Snapshot:
    """Construit un snapshot directement depuis data/export_plateforme.json (tests, import à blanc)."""
    from datetime import date as _d

    def pd(s):
        return _d.fromisoformat(s) if s else None

    snap = Snapshot()
    snap.clients = [Client(c["id"], c["name"]) for c in data["clients"]]
    for p in data["projects"]:
        snap.projects.append(
            Project(
                id=p["id"],
                client_id=p["client_id"],
                name=p["name"],
                billing_type=p["billing_type"],
                monthly_amount=Decimal(str(p.get("monthly_amount") or 0)),
                quote_amount=Decimal(str(p["quote_amount"])) if p.get("quote_amount") else None,
                cost=Decimal(str(p.get("cost") or 0)),
                start_month=p["start_month"],
                end_month=p.get("end_month") or "",
                status=p["status"],
                note=p.get("note", ""),
            )
        )
    for i in data["invoices"]:
        pay = i.get("payment") or {}
        snap.invoices.append(
            Invoice(
                id=i["id"],
                project_id=i["project_id"],
                service_month=i["service_month"],
                amount=Decimal(str(i["amount"])),
                label=i.get("label", ""),
                kind=i.get("kind", "invoice"),
                status=i["status"],
                due_date=pd(pay.get("due_date")),
                payment_status=pay.get("status", "pending"),
                paid_on=pd(pay.get("paid_on")),
                has_document=bool(i.get("document")),
                document_name=(i.get("document") or "").split("/")[-1],
            )
        )
    occ: dict[tuple, FixedOccurrence] = {}

    def get(pid, m):
        return occ.setdefault((pid, m), FixedOccurrence(pid, m))

    for o in data.get("fixed_overrides", []):
        get(o["project_id"], o["month"]).override_amount = Decimal(str(o["amount"]))
    for o in data.get("fixed_billed_marks", []):
        get(o["project_id"], o["month"]).billed_marked = True
    for o in data.get("payments", []):
        x = get(o["project_id"], o["month"])
        if o["ref"] == "fixed":
            x.payment_status = o.get("status", "pending")
            x.due_date = pd(o.get("due_date"))
            x.paid_on = pd(o.get("paid_on"))
        elif o["ref"] == "fixed_document":
            x.has_document = True
            x.document_name = (o.get("document") or "").split("/")[-1]
    snap.occurrences = list(occ.values())
    for x in data.get("expenses", []):
        snap.expenses.append(
            Expense(
                id=x["id"],
                date=pd(x["date"]),
                supplier=x["supplier"],
                category=x.get("category", "Autres"),
                label=x.get("label", ""),
                project_id=x.get("projectId") or x.get("project_id") or None,
                amount_ht=Decimal(str(x.get("ht") or x.get("amount_ht") or 0)),
                vat=Decimal(str(x.get("tva") or x.get("vat") or 0)),
                has_receipt=bool(x.get("fileId") or x.get("receipt")),
                receipt_name=x.get("fileName", ""),
            )
        )
    return snap
