"""Create demo data: Digitalia team, three clients, projects, roadmaps and tickets."""
import datetime

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from core.models import Company, Milestone, Project, User
from tickets.models import Comment, Ticket
from tickets.services import record_creation

PASSWORD = "orbit-demo"


class Command(BaseCommand):
    help = "Load demo data (users share the password 'orbit-demo')."

    @transaction.atomic
    def handle(self, *args, **options):
        today = timezone.localdate()
        day = datetime.timedelta(days=1)

        def user(username, first, last, company, role=User.Role.CLIENT, **extra):
            u, created = User.objects.get_or_create(
                username=username,
                defaults=dict(first_name=first, last_name=last, email=f"{username}@example.com",
                              company=company, role=role, **extra),
            )
            if created:
                u.set_password(PASSWORD)
                u.save()
            return u

        digitalia, _ = Company.objects.get_or_create(name="Digitalia", defaults={"is_internal": True})
        admin = user("admin", "Admin", "Digitalia", digitalia, User.Role.STAFF, is_staff=True, is_superuser=True)
        dev = user("sara", "Sara", "Dev", digitalia, User.Role.STAFF)
        pm = user("yanis", "Yanis", "PM", digitalia, User.Role.STAFF, is_staff=True)

        specs = [
            ("WWS", "Smart CV", "SCV", "wws", "Julie", "Martin"),
            ("RM Club", "RM Club", "RMC", "rmclub", "Karim", "Benali"),
            ("Bodytime", "TWM", "TWM", "bodytime", "Lina", "Morel"),
        ]
        for company_name, project_name, key, username, first, last in specs:
            company, _ = Company.objects.get_or_create(name=company_name)
            client = user(username, first, last, company)
            project, created = Project.objects.get_or_create(
                key=key, defaults={"company": company, "name": project_name, "lead": pm,
                                   "description": f"Projet {project_name} pour {company_name}."},
            )
            project.members.add(client)
            if not created:
                continue
            v1 = Milestone.objects.create(project=project, name="2.3", status=Milestone.Status.DONE,
                                          start_date=today - 60 * day, due_date=today - 20 * day)
            v2 = Milestone.objects.create(project=project, name="2.4", status=Milestone.Status.IN_PROGRESS,
                                          start_date=today - 20 * day, due_date=today + 15 * day)
            Milestone.objects.create(project=project, name="3.0", start_date=today + 15 * day, due_date=today + 75 * day)

            def ticket(author, **fields):
                t = Ticket.objects.create(project=project, author=author, **fields)
                record_creation(t, author)
                return t

            ticket(client, title="Export PDF des résultats", type=Ticket.Type.EVOLUTION,
                   status=Ticket.Status.DONE, milestone=v1, description="Pouvoir exporter les résultats en PDF.")
            ticket(client, title="Erreur 500 à la connexion", type=Ticket.Type.BUG, priority=Ticket.Priority.HIGH,
                   status=Ticket.Status.IN_PROGRESS, milestone=v2, assignee=dev, due_date=today - 2 * day,
                   description="Depuis ce matin, la connexion renvoie une erreur 500.")
            parent = ticket(client, title="Campagnes de formation", type=Ticket.Type.FEATURE,
                            status=Ticket.Status.TODO, milestone=v2, assignee=pm, due_date=today + 10 * day,
                            description="Créer et suivre des campagnes de formation.")
            for label in ("Développement", "Tests", "Mise en production"):
                ticket(dev, title=f"{label} — campagnes", type=Ticket.Type.TASK, parent=parent, milestone=v2,
                       visibility=Ticket.Visibility.INTERNAL, status=Ticket.Status.TODO, assignee=dev)
            waiting = ticket(client, title="Logo à mettre à jour", type=Ticket.Type.QUESTION,
                             status=Ticket.Status.WAITING_CLIENT, assignee=pm)
            Comment.objects.create(ticket=waiting, author=pm, body="Pouvez-vous nous envoyer le logo en SVG ?")
            ticket(dev, title="Refactor API authentication", type=Ticket.Type.TASK,
                   visibility=Ticket.Visibility.INTERNAL, status=Ticket.Status.TODO, assignee=dev, milestone=v2)
            ticket(client, title="Nouvelle page statistiques", type=Ticket.Type.EVOLUTION,
                   status=Ticket.Status.NEW, description="Ajouter une page de statistiques mensuelles.")

        self.stdout.write(self.style.SUCCESS(
            f"Demo data ready. Log in as admin / sara / yanis (Digitalia) or wws / rmclub / bodytime (clients), "
            f"password: {PASSWORD}"
        ))
