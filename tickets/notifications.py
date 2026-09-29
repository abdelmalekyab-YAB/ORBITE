"""E-mail notifications: tell the right person when the ball changes side."""
from django.conf import settings
from django.core.mail import send_mail
from django.db import transaction
from django.db.models import Q
from django.utils import translation
from django.utils.translation import gettext as _

from .models import Ticket

S = Ticket.Status


def _url(ticket):
    return settings.ORBIT_BASE_URL.rstrip("/") + ticket.get_absolute_url()


def _emails(users, exclude=None):
    return sorted({u.email for u in users if u and u.is_active and u.email and u != exclude})


def _client_recipients(ticket, exclude=None):
    if ticket.visibility != Ticket.Visibility.CLIENT:
        return []
    return _emails(ticket.project.members.all(), exclude)


def _digitalia_recipients(ticket, exclude=None):
    """The assignee, else the project lead, else every Digitalia admin."""
    from core.models import User

    if ticket.assignee:
        people = [ticket.assignee]
    elif ticket.project.lead:
        people = [ticket.project.lead]
    else:
        people = list(User.objects.filter(Q(role="staff") | Q(is_superuser=True), is_staff=True))
    return _emails(people, exclude)


def _send(recipients, subject, body):
    if not recipients:
        return
    transaction.on_commit(lambda: send_mail(
        subject, body, settings.DEFAULT_FROM_EMAIL, recipients, fail_silently=True,
    ))


def _mail(recipients, ticket, subject, lines):
    with translation.override(settings.LANGUAGE_CODE):
        body = "\n\n".join([*lines, _("Open the ticket: %(url)s") % {"url": _url(ticket)}, "— Orbit, Digitalia"])
        _send(recipients, f"[Orbit] {ticket.reference} · {subject}", body)


def status_changed(ticket, old_status, actor):
    new = ticket.status
    with translation.override(settings.LANGUAGE_CODE):
        if new == S.WAITING_CLIENT:
            _mail(_client_recipients(ticket, actor), ticket, _("Digitalia needs your answer"), [
                _("Hello,"),
                _("Digitalia is waiting for your answer on “%(title)s”.") % {"title": ticket.title},
                _("Reply directly in Orbit, then click “I answered”."),
            ])
        elif new == S.IN_TEST:
            _mail(_client_recipients(ticket, actor), ticket, _("Ready for you to test"), [
                _("Hello,"),
                _("“%(title)s” is ready. Please test it and tell us the result in Orbit (Test OK / Not OK).")
                % {"title": ticket.title},
            ])
        elif actor is not None and not actor.is_digitalia and old_status in (S.WAITING_CLIENT, S.IN_TEST, S.DONE):
            last = ticket.comments.filter(author=actor).order_by("-created_at").first()
            what = {
                S.TO_ANALYSE: _("The client answered"),
                S.DONE: _("The client approved the test"),
                S.IN_PROGRESS: _("The client says it is NOT OK"),
            }.get(new, _("The client updated the ticket"))
            lines = [f"{what} : {actor} ({actor.company or ''})."]
            if last:
                lines.append(_("Client message:") + f"\n{last.body}")
            _mail(_digitalia_recipients(ticket, actor), ticket, what, lines)


def ticket_created(ticket):
    if ticket.origin != Ticket.Origin.CLIENT:
        return
    with translation.override(settings.LANGUAGE_CODE):
        _mail(_digitalia_recipients(ticket, ticket.author), ticket,
              _("New client request: %(type)s") % {"type": ticket.get_type_display()}, [
                  _("%(author)s (%(company)s) created a request on %(project)s:")
                  % {"author": ticket.author, "company": ticket.author_company or "", "project": ticket.project.name},
                  f"{ticket.title}\n\n{ticket.description}",
              ])


def comment_added(comment):
    ticket, author = comment.ticket, comment.author
    if comment.is_internal or author is None:
        return
    with translation.override(settings.LANGUAGE_CODE):
        if author.is_digitalia:
            _mail(_client_recipients(ticket, author), ticket, _("New message from Digitalia"),
                  [_("%(author)s wrote:") % {"author": author}, comment.body])
        else:
            _mail(_digitalia_recipients(ticket, author), ticket, _("New message from the client"),
                  [_("%(author)s wrote:") % {"author": author}, comment.body])
