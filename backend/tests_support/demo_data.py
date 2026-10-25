"""Jeu de données des TESTS AUTOMATISÉS uniquement (fixture `seeded` de conftest.py).
Reprend la maquette pour vérifier les règles métier et les chiffres attendus. Jamais chargé dans l'application :
la base réelle ne contient que ce qui est saisi dans Orbit."""
from datetime import date, datetime
from decimal import Decimal
from typing import Any
from zoneinfo import ZoneInfo

from django.db import transaction

from apps.accounts.models import Organization, User
from apps.finance.models import DevInstallment, FinanceSettings, ProjectFinance, StaffAllocation, StaffCost
from apps.notifications.service import muted as notifications_muted
from apps.projects.models import Milestone, Project, ProjectAccess
from apps.tickets import workflow
from apps.tickets.models import Comment, Quote, QuoteInstallment, Ticket, TicketEvent

PARIS = ZoneInfo("Europe/Paris")

DEMO = [
    ("Digitalia", "digitalia", [("admin@digitalia.io", "Yasmina", "A.", "admin"),
                                ("yanis@digitalia.io", "Yanis", "PM", "pm"),
                                ("sara@digitalia.io", "Sara", "Dev", "dev")]),
    ("WWS", "client", [("julie@wws.fr", "Julie", "Martin", "client")]),
    ("RM Club", "client", [("marc@rmclub.fr", "Marc", "Leroy", "client")]),
    ("Bodytime", "client", [("nadia@bodytime.ma", "Nadia", "Benali", "client")]),
]
# key, nom, client, responsable, description, utilisateurs clients ayant accès
PROJECTS = [
    ("SCV", "Smart CV", "WWS", "yanis", "Plateforme de génération de CV et campagnes de formation.", ["julie"]),
    ("CHK", "Checklists", "WWS", "sara", "Digitalisation des checklists terrain sur tablette.", ["julie"]),
    ("RMC", "RM Club", "RM Club", "yanis", "Gestion de club, adhérents et abonnements.", ["marc"]),
    ("TWM", "TWM", "Bodytime", "yanis", "Application mobile nutrition et suivi.", ["nadia"]),
]
MILESTONES = [("Version 2.3", date(2026, 7, 31), date(2026, 9, 9)),
              ("Version 2.4", date(2026, 9, 9), date(2026, 10, 14)),
              ("Version 3.0", date(2026, 10, 14), date(2026, 12, 13))]
CLIENT_OF = {"SCV": "julie", "CHK": "julie", "RMC": "marc", "TWM": "nadia"}
# Finances de la maquette : prix du dev, échéances (date, montant, encaissée), licence (montant, début), coûts.
FINANCE: dict[str, dict[str, Any]] = {
    "SCV": dict(dev_price=18000, licence_amount=890, licence_start=date(2026, 8, 1), cost_mode="people",
                schedule=[(date(2026, 5, 15), 5400, True), (date(2026, 7, 15), 7200, True),
                          (date(2026, 10, 15), 5400, False)]),
    "RMC": dict(dev_price=9500, licence_amount=590, licence_start=date(2026, 7, 1), cost_mode="monthly",
                cost_monthly=900, schedule=[(date(2026, 6, 1), 9500, True)]),
    "TWM": dict(dev_price=32000, licence_amount=1290, licence_start=date(2026, 6, 1), cost_mode="days",
                cost_days=112, cost_tjm=450, cost_month=date(2026, 3, 1),
                schedule=[(date(2026, 3, 1), 9600, True), (date(2026, 5, 1), 9600, True),
                          (date(2026, 7, 1), 6400, True), (date(2026, 11, 1), 6400, False)]),
    "CHK": dict(dev_price=12000, licence_amount=450, licence_start=date(2026, 9, 1), cost_mode="none",
                schedule=[(date(2026, 8, 1), 6000, True), (date(2026, 12, 1), 6000, False)]),
}
STAFF = {"sara": (3600, {"TWM": 50, "SCV": 30, "RMC": 20}), "yanis": (4200, {"TWM": 30, "SCV": 40, "RMC": 30})}


def at(value: str) -> datetime:
    return datetime.fromisoformat(value).replace(tzinfo=PARIS)


def project_set(key: str) -> list[dict]:
    """Jeu de tickets commun à SCV / RMC / TWM (variantes comme dans la maquette)."""
    client = CLIENT_OF[key]
    scv = key == "SCV"
    return [
        dict(n=1, author=client, type="evolution", title="Export PDF des résultats",
             description="Pouvoir exporter les résultats en PDF.", status="termine", ms="Version 2.3",
             billing="licence", estimate_days=1),
        dict(n=2, author=client, type="bug", title="Erreur 500 à la connexion",
             description="Depuis ce matin, la connexion renvoie une erreur 500 pour tous les utilisateurs.",
             status="cours", priority="high", assignee="sara", due_on=date(2026, 9, 27), ms="Version 2.4"),
        dict(n=3, author=client, type="feature", title="Campagnes de formation",
             description="Créer et suivre des campagnes de formation.", status="devis" if scv else "faire",
             assignee="yanis", due_on=date(2026, 10, 9), ms="Version 2.4", billing="quote", estimate_days=6),
        dict(n=4, author="yanis", internal=True, type="internal", title="Développement — campagnes", status="faire",
             assignee="sara", parent=3),
        dict(n=5, author="yanis", internal=True, type="internal", title="Tests — campagnes", status="faire",
             assignee="sara", parent=3),
        dict(n=6, author="yanis", internal=True, type="internal", title="Mise en production — campagnes",
             status="faire", assignee="sara", parent=3),
        dict(n=7, author=client, type="question", title="Logo à mettre à jour", status="attente", assignee="yanis",
             comments=[("yanis", "Pouvez-vous nous envoyer le logo en SVG ?", "2026-09-29T15:55")]),
        dict(n=8, author="sara", internal=True, type="internal", title="Refactor API authentication", status="faire",
             assignee="sara"),
        dict(n=9, author=client, type="evolution", title="Nouvelle page statistiques",
             description="Ajouter une page de statistiques mensuelles.", status="faire" if scv else "nouveau",
             billing="licence", estimate_days=2.5),
        dict(n=10, author=client, type="evolution", title="Filtre par date sur les résultats",
             description="Pouvoir filtrer les résultats par période.", status="test" if scv else "cours",
             assignee="sara", due_on=date(2026, 10, 2), ms="Version 2.4", billing="licence", estimate_days=1.5,
             created="2026-09-29T17:08",
             comments=[("sara", "C'est disponible sur la préproduction, pouvez-vous tester et nous dire si c'est "
                                "bon ?", "2026-09-29T17:08")]
             + ([("nadia", "Merci, je regarde ça demain matin.", "2026-09-29T17:20")] if key == "TWM" else [])),
    ]


CHK_TICKETS = [
    dict(n=1, author="julie", type="bug", title="Photo non enregistrée hors connexion",
         description="Quand la tablette n'a pas de réseau, la photo prise dans la checklist disparaît à la "
                     "synchronisation.", status="cours", priority="high", assignee="sara", due_on=date(2026, 10, 3),
         ms="Version 2.4", billing="licence"),
    dict(n=2, author="julie", type="evolution", title="Signature du technicien en fin de checklist",
         description="Ajouter une zone de signature avant validation.", status="nouveau", billing="licence"),
    dict(n=3, author="julie", type="question", title="Combien de tablettes peut-on connecter ?", status="termine",
         closed="2026-09-20T10:00"),
    dict(n=4, author="sara", origin="digitalia", type="feature", title="Export des checklists en PDF",
         status="testint", assignee="sara", ms="Version 2.4", billing="licence"),
]


def load_demo() -> None:
    """Charge le jeu de test (idempotent)."""
    with notifications_muted(), transaction.atomic():
        _DemoLoader()._handle()


class _DemoLoader:

    def _handle(self):
        users: dict[str, User] = {}
        for org_name, kind, members in DEMO:
            org, _ = Organization.objects.get_or_create(name=org_name, defaults={"kind": kind})
            for email, first, last, job in members:
                user, created = User.objects.get_or_create(email=email, defaults={
                    "username": email, "first_name": first, "last_name": last, "organization": org, "job": job,
                    "is_staff": job == "admin", "is_superuser": job == "admin"})
                if created:
                    user.set_password("orbit")
                    user.save()
                users[email.split("@")[0]] = user

        for key, name, client, lead, desc, access in PROJECTS:
            project, _ = Project.objects.get_or_create(key=key, defaults={
                "name": name, "description": desc, "client": Organization.objects.get(name=client),
                "lead": users[lead]})
            for u in access:
                ProjectAccess.objects.get_or_create(user=users[u], project=project)
            for order, (ms_name, start, end) in enumerate(MILESTONES, start=1):
                Milestone.objects.get_or_create(project=project, name=ms_name,
                                                defaults={"starts_on": start, "ends_on": end, "order": order})
            if project.ticket_seq == 0:
                self._tickets(project, CHK_TICKETS if key == "CHK" else project_set(key), users)
        self._quotes(users)
        self._finance(users)

    def _quotes(self, users):
        """Devis de la maquette : SCV-3 envoyé, RMC-3 accepté (échéances fixées comme dans la maquette)."""
        scv3 = Ticket.objects.get(project__key="SCV", number=3)
        if not hasattr(scv3, "quote"):
            Quote.objects.create(ticket=scv3, amount_ht=Decimal("3600"), parts=2, status=Quote.Status.SENT,
                                 sent_at=at("2026-09-29T16:00"),
                                 description="Module campagnes de formation : création, planning, suivi des "
                                             "participants et export. Livraison en version 2.4.")
            TicketEvent.objects.create(ticket=scv3, actor=users["yanis"], kind="quote_sent", to_value="3600.00",
                                       message="a envoyé une proposition commerciale (3600.00 € HT)",
                                       at=at("2026-09-29T16:00"))
        rmc3 = Ticket.objects.get(project__key="RMC", number=3)
        if not hasattr(rmc3, "quote"):
            q = Quote.objects.create(ticket=rmc3, amount_ht=Decimal("2900"), parts=2, status=Quote.Status.ACCEPTED,
                                     description="Module campagnes de formation.", sent_at=at("2026-09-20T10:00"),
                                     decided_at=at("2026-09-24T09:00"), decided_by=users["marc"])
            QuoteInstallment.objects.create(quote=q, due_on=date(2026, 9, 24), amount=Decimal("1450"), is_paid=True,
                                            paid_on=date(2026, 9, 24))
            QuoteInstallment.objects.create(quote=q, due_on=date(2026, 11, 24), amount=Decimal("1450"))
            TicketEvent.objects.create(ticket=rmc3, actor=users["marc"], kind="quote_accepted", to_value="2900.00",
                                       message="a accepté la proposition commerciale (2900.00 € HT)",
                                       at=at("2026-09-24T09:00"))

    def _tickets(self, project, specs, users):
        by_number: dict[int, Ticket] = {}
        for spec in sorted(specs, key=lambda s: s["n"]):
            author = users[spec["author"]]
            internal = spec.get("internal", False)
            created = at(spec.get("created", "2026-09-29T15:55"))
            ticket = workflow.create_ticket(
                project=project, author=author, status_key=spec["status"], type=spec["type"], title=spec["title"],
                description=spec.get("description", ""), priority=spec.get("priority", "normal"),
                origin=spec.get("origin") or ("digitalia" if author.is_digitalia else "client"),
                is_internal=internal, assignee=users.get(spec.get("assignee", "")), due_on=spec.get("due_on"),
                milestone=project.milestones.filter(name=spec.get("ms")).first() if spec.get("ms") else None,
                parent=by_number.get(spec.get("parent")), billing=spec.get("billing"),
                estimate_days=spec.get("estimate_days"), created_at=created)
            if ticket.status.is_closed:
                ticket.closed_at = at(spec.get("closed", "2026-09-29T15:55"))
                ticket.save(update_fields=["closed_at"])
            TicketEvent.objects.filter(ticket=ticket).update(at=created)
            for who, body, when in spec.get("comments", []):
                c = workflow.add_comment(ticket, users[who], body)
                Comment.objects.filter(pk=c.pk).update(created_at=at(when))
                TicketEvent.objects.filter(ticket=ticket, kind="comment").update(at=at(when))
            by_number[spec["n"]] = ticket

    def _finance(self, users):
        FinanceSettings.objects.update_or_create(pk=1, defaults={"default_tjm": Decimal("450")})
        for key, spec in FINANCE.items():
            spec = dict(spec)
            schedule = spec.pop("schedule")
            fin, created = ProjectFinance.objects.get_or_create(project=Project.objects.get(key=key), defaults=spec)
            if created:
                for due_on, amount, paid in schedule:
                    DevInstallment.objects.create(finance=fin, due_on=due_on, amount=Decimal(amount), is_paid=paid,
                                                  paid_on=due_on if paid else None)
        for login, (salary, allocations) in STAFF.items():
            sc, created = StaffCost.objects.get_or_create(user=users[login],
                                                          defaults={"monthly_salary": Decimal(salary)})
            if created:
                for key, percent in allocations.items():
                    StaffAllocation.objects.create(staff_cost=sc, project=Project.objects.get(key=key), percent=percent)
