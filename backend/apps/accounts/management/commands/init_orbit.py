"""Initialisation d'une base vide : organisation Digitalia + premier administrateur.

    python manage.py init_orbit --email prenom@digitalia-ltd.com --name "Prénom Nom"

Aucun mot de passe n'est choisi ici : l'administrateur reçoit un lien d'invitation (e-mail + affiché ci-dessous)
et définit lui-même son mot de passe. Tout le reste (clients, projets, utilisateurs, tickets) se saisit dans Orbit.
"""
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.accounts import invitations
from apps.accounts.models import Organization, User
from apps.accounts.serializers import split_name


class Command(BaseCommand):
    help = "Crée l'organisation Digitalia et invite le premier administrateur (base vide)."

    def add_arguments(self, parser):
        parser.add_argument("--email", required=True, help="E-mail de l'administrateur")
        parser.add_argument("--name", required=True, help="Prénom et nom de l'administrateur")
        parser.add_argument("--organization", default="Digitalia", help="Nom de l'organisation (défaut : Digitalia)")

    def handle(self, *args, email: str, name: str, organization: str, **options):
        email = email.strip().lower()
        if User.objects.filter(email__iexact=email).exists():
            raise CommandError(f"Un compte existe déjà pour {email}.")
        with transaction.atomic():
            org = Organization.objects.filter(kind=Organization.Kind.DIGITALIA).first()
            if org is None:
                org = Organization.objects.create(name=organization, kind=Organization.Kind.DIGITALIA)
            first, last = split_name(name)
            user = User(email=email, username=email, first_name=first, last_name=last, organization=org,
                        job=User.Job.ADMIN, is_staff=True, is_superuser=True)
            user.set_unusable_password()
            user.save()
            invitations.send_invitation(user)
        self.stdout.write(self.style.SUCCESS(f"Administrateur {user.get_full_name()} créé dans « {org.name} »."))
        self.stdout.write("Lien pour définir le mot de passe (valable 7 jours, usage unique) :")
        self.stdout.write(invitations.link(user, "invitation"))
