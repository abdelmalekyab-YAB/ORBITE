"""Invitation et réinitialisation du mot de passe (règle 4). Les liens sont à usage unique : le jeton
dépend du mot de passe, il devient invalide dès que celui-ci est défini."""
from django.conf import settings
from django.contrib.auth.tokens import default_token_generator
from django.db import transaction
from django.utils import timezone
from django.utils.encoding import force_bytes, force_str
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode

from .models import User


def link(user: User, path: str) -> str:
    uid = urlsafe_base64_encode(force_bytes(user.pk))
    token = default_token_generator.make_token(user)
    return f"{settings.FRONTEND_URL}/{path}?uid={uid}&token={token}"


def user_from_token(uid: str, token: str) -> User | None:
    try:
        user = User.objects.get(pk=force_str(urlsafe_base64_decode(uid)))
    except (User.DoesNotExist, ValueError, TypeError, OverflowError):
        return None
    return user if default_token_generator.check_token(user, token) else None


def _send(to: str, subject: str, body: str):
    from apps.notifications.tasks import send_email

    transaction.on_commit(lambda: send_email.delay(to, subject, body))


def send_invitation(user: User, invited_by: User | None = None) -> None:
    user.invited_at = timezone.now()
    user.save(update_fields=["invited_at"])
    who = f"{invited_by.get_full_name()} vous invite" if invited_by else "Digitalia vous invite"
    _send(user.email, "Votre accès à Orbit",
          f"Bonjour {user.first_name},\n\n{who} à rejoindre Orbit, l'espace de suivi de vos projets avec Digitalia.\n\n"
          f"Créez votre mot de passe ici (lien valable 7 jours) :\n{link(user, 'invitation')}\n\n— L'équipe Digitalia")


def send_password_reset(user: User) -> None:
    _send(user.email, "Réinitialisation de votre mot de passe Orbit",
          f"Bonjour {user.first_name},\n\nPour choisir un nouveau mot de passe, ouvrez ce lien (valable 7 jours) :\n"
          f"{link(user, 'reinitialiser')}\n\nSi vous n'êtes pas à l'origine de cette demande, ignorez ce message.\n\n"
          "— L'équipe Digitalia")
