"""Invitations and password links, sent by e-mail."""
from django.conf import settings
from django.contrib.auth.tokens import default_token_generator
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode


def password_link(request, user, view_name="welcome"):
    uid = urlsafe_base64_encode(force_bytes(user.pk))
    token = default_token_generator.make_token(user)
    return request.build_absolute_uri(reverse(view_name, args=[uid, token]))


def send_invitation(request, user, invited_by):
    context = {
        "user": user,
        "invited_by": invited_by,
        "link": password_link(request, user),
        "projects": list(user.projects.all()),
        "login_url": request.build_absolute_uri(reverse("login")),
    }
    subject = render_to_string("registration/invitation_subject.txt", context).strip()
    body = render_to_string("registration/invitation_email.txt", context)
    send_mail(subject, body, settings.DEFAULT_FROM_EMAIL, [user.email])


def is_pending(user):
    """Invited but never set a password."""
    return not user.has_usable_password() and user.last_login is None
