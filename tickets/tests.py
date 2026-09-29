import datetime
import json
import shutil
import tempfile

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from core.models import Company, Milestone, Project, User

from .models import Attachment, Comment, Ticket, TicketEvent
from .services import ticket_stats

MEDIA = tempfile.mkdtemp()


@override_settings(MEDIA_ROOT=MEDIA, LANGUAGE_CODE="en")
class OrbitTests(TestCase):
    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(MEDIA, ignore_errors=True)
        super().tearDownClass()

    @classmethod
    def setUpTestData(cls):
        cls.digitalia = Company.objects.create(name="Digitalia", is_internal=True)
        cls.wws = Company.objects.create(name="WWS")
        cls.other = Company.objects.create(name="Other")
        cls.staff = User.objects.create_user("staff", password="x", role=User.Role.STAFF, company=cls.digitalia)
        cls.client_user = User.objects.create_user("client", password="x", company=cls.wws)
        cls.intruder = User.objects.create_user("intruder", password="x", company=cls.other)
        cls.project = Project.objects.create(company=cls.wws, name="Smart CV", key="scv")
        cls.project.members.add(cls.client_user)
        cls.other_project = Project.objects.create(company=cls.other, name="Other", key="OTH")
        cls.other_project.members.add(cls.intruder)
        cls.milestone = Milestone.objects.create(project=cls.project, name="2.4")

    def url(self, name, *args):
        return reverse(name, args=args)

    def test_project_key_uppercased_and_numbering(self):
        self.assertEqual(self.project.key, "SCV")
        t1 = Ticket.objects.create(project=self.project, title="a", author=self.client_user)
        t2 = Ticket.objects.create(project=self.project, title="b", author=self.staff)
        t3 = Ticket.objects.create(project=self.other_project, title="c", author=self.intruder)
        self.assertEqual((t1.number, t2.number, t3.number), (1, 2, 1))
        self.assertEqual(t1.reference, "SCV-1")

    def test_origin_and_forced_visibility(self):
        t = Ticket.objects.create(project=self.project, title="a", author=self.client_user,
                                  visibility=Ticket.Visibility.INTERNAL)
        self.assertEqual(t.origin, Ticket.Origin.CLIENT)
        self.assertEqual(t.visibility, Ticket.Visibility.CLIENT)
        self.assertEqual(t.author_company, self.wws)
        self.assertEqual(Ticket.objects.create(project=self.project, title="b", author=self.staff).origin, "digitalia")
        self.assertEqual(Ticket.objects.create(project=self.project, title="c").origin, "system")

    def test_client_home_redirects_to_single_project(self):
        self.client.force_login(self.client_user)
        self.assertRedirects(self.client.get("/"), self.url("project_board", "SCV"))

    def test_staff_home_goes_to_dashboard(self):
        self.client.force_login(self.staff)
        self.assertRedirects(self.client.get("/"), self.url("dashboard"))

    def test_client_cannot_see_other_projects_or_staff_pages(self):
        self.client.force_login(self.intruder)
        self.assertEqual(self.client.get(self.url("project_detail", "SCV")).status_code, 404)
        self.assertEqual(self.client.get(self.url("project_tickets", "SCV")).status_code, 404)
        self.assertEqual(self.client.get(self.url("dashboard")).status_code, 403)
        self.assertEqual(self.client.get(self.url("all_tickets")).status_code, 403)

    def test_client_creates_request(self):
        self.client.force_login(self.client_user)
        upload = SimpleUploadedFile("screen.png", b"\x89PNG fake", content_type="image/png")
        response = self.client.post(self.url("ticket_create", "SCV"), {
            "type": "bug", "title": "Crash", "description": "It crashes", "priority": "high", "files": [upload],
        })
        ticket = Ticket.objects.get()
        self.assertRedirects(response, ticket.get_absolute_url())
        self.assertEqual((ticket.origin, ticket.author, ticket.project), ("client", self.client_user, self.project))
        self.assertEqual(ticket.attachments.count(), 1)
        self.assertTrue(ticket.events.filter(kind=TicketEvent.Kind.CREATED).exists())

    def test_client_cannot_create_internal_task_type(self):
        self.client.force_login(self.client_user)
        self.client.post(self.url("ticket_create", "SCV"), {"type": "task", "title": "x", "description": "y", "priority": "normal"})
        self.assertFalse(Ticket.objects.exists())

    def test_internal_tickets_comments_and_files_hidden_from_client(self):
        internal = Ticket.objects.create(project=self.project, title="Refactor API authentication",
                                         author=self.staff, visibility=Ticket.Visibility.INTERNAL)
        public = Ticket.objects.create(project=self.project, title="Public", author=self.staff)
        Comment.objects.create(ticket=public, author=self.staff, body="secret note", is_internal=True)
        Comment.objects.create(ticket=public, author=self.staff, body="hello client")
        secret_file = Attachment.objects.create(ticket=public, uploaded_by=self.staff, is_internal=True,
                                                file=SimpleUploadedFile("secret.txt", b"s"))
        self.client.force_login(self.client_user)
        listing = self.client.get(self.url("project_tickets", "SCV")).content.decode()
        self.assertNotIn("Refactor API authentication", listing)
        self.assertIn("Public", listing)
        self.assertEqual(self.client.get(internal.get_absolute_url()).status_code, 404)
        detail = self.client.get(public.get_absolute_url()).content.decode()
        self.assertIn("hello client", detail)
        self.assertNotIn("secret note", detail)
        self.assertEqual(self.client.get(self.url("attachment_download", secret_file.pk)).status_code, 403)
        self.client.force_login(self.staff)
        self.assertIn("secret note", self.client.get(public.get_absolute_url()).content.decode())

    def test_client_reply_moves_waiting_ticket_back(self):
        ticket = Ticket.objects.create(project=self.project, title="Q", author=self.staff,
                                       status=Ticket.Status.WAITING_CLIENT)
        self.client.force_login(self.client_user)
        self.client.post(ticket.get_absolute_url(), {"body": "Here is the answer"})
        ticket.refresh_from_db()
        self.assertEqual(ticket.status, Ticket.Status.TO_ANALYSE)
        self.assertEqual(ticket.comments.get().is_internal, False)

    def test_client_cannot_post_internal_comment_or_edit(self):
        ticket = Ticket.objects.create(project=self.project, title="Q", author=self.client_user)
        self.client.force_login(self.client_user)
        self.client.post(ticket.get_absolute_url(), {"body": "hi", "is_internal": "on"})
        self.assertFalse(ticket.comments.get().is_internal)
        self.assertEqual(self.client.get(self.url("ticket_edit", "SCV", ticket.number)).status_code, 403)

    def test_staff_edit_records_history(self):
        ticket = Ticket.objects.create(project=self.project, title="Old", author=self.client_user)
        self.client.force_login(self.staff)
        response = self.client.post(self.url("ticket_edit", "SCV", ticket.number), {
            "type": "bug", "title": "New", "description": "", "status": "in_progress", "priority": "high",
            "visibility": "client", "assignee": self.staff.pk, "milestone": self.milestone.pk, "parent": "", "due_date": "",
        })
        self.assertRedirects(response, ticket.get_absolute_url())
        changed = set(ticket.events.filter(kind=TicketEvent.Kind.CHANGED).values_list("field", flat=True))
        self.assertEqual(changed, {"title", "type", "status", "priority", "assignee", "milestone"})

    def test_staff_subtask_and_internal_ticket(self):
        parent = Ticket.objects.create(project=self.project, title="Campagnes", author=self.client_user)
        self.client.force_login(self.staff)
        self.client.post(self.url("ticket_create", "SCV") + "?parent=1", {
            "type": "task", "title": "Dev", "description": "", "status": "todo", "priority": "normal",
            "visibility": "internal", "assignee": "", "milestone": "", "parent": parent.pk, "due_date": "",
        })
        sub = Ticket.objects.get(title="Dev")
        self.assertEqual((sub.parent, sub.origin, sub.visibility), (parent, "digitalia", "internal"))

    def test_stats_and_dashboard(self):
        today = timezone.localdate()
        Ticket.objects.create(project=self.project, title="bug", type="bug", author=self.client_user,
                              due_date=today - datetime.timedelta(days=1))
        Ticket.objects.create(project=self.project, title="wait", status="waiting_client", author=self.staff)
        Ticket.objects.create(project=self.project, title="done", status="done", author=self.staff)
        stats = ticket_stats(Ticket.objects.filter(project=self.project))
        self.assertEqual((stats["open"], stats["bugs"], stats["late"], stats["waiting_client"], stats["done"]),
                         (2, 1, 1, 1, 1))
        self.client.force_login(self.staff)
        self.assertContains(self.client.get(self.url("dashboard")), "Smart CV")

    def test_filters(self):
        Ticket.objects.create(project=self.project, title="A bug", type="bug", author=self.client_user)
        Ticket.objects.create(project=self.other_project, title="Other evo", author=self.intruder)
        self.client.force_login(self.staff)
        response = self.client.get(self.url("all_tickets"), {"company": self.wws.pk, "type": "bug"})
        self.assertContains(response, "A bug")
        self.assertNotContains(response, "Other evo")
        self.assertContains(self.client.get(self.url("all_tickets"), {"q": "SCV-1"}), "A bug")

    def test_dashboard_counters_open_the_matching_tickets(self):
        Ticket.objects.create(project=self.project, title="Evo one", type="evolution", author=self.client_user)
        Ticket.objects.create(project=self.project, title="Feature two", type="feature", author=self.client_user)
        Ticket.objects.create(project=self.project, title="Bug three", type="bug", author=self.client_user)
        Ticket.objects.create(project=self.project, title="Testing four", status="in_test", author=self.staff)
        self.client.force_login(self.staff)
        dashboard = self.client.get(self.url("dashboard")).content.decode()
        self.assertIn('href="/tickets/?type=changes"', dashboard)
        changes = self.client.get(self.url("all_tickets"), {"type": "changes"})
        self.assertContains(changes, "Evo one")
        self.assertContains(changes, "Feature two")
        self.assertNotContains(changes, "Bug three")
        working = self.client.get(self.url("all_tickets"), {"status": "working"})
        self.assertContains(working, "Testing four")
        self.assertNotContains(working, "Evo one")
        self.client.force_login(self.client_user)
        self.assertContains(self.client.get(self.url("project_tickets", "SCV"), {"type": "changes"}), "Feature two")

    def test_pages_render(self):
        Ticket.objects.create(project=self.project, title="t", author=self.client_user, milestone=self.milestone)
        for user in (self.staff, self.client_user):
            self.client.force_login(user)
            for name in ("project_detail", "roadmap", "project_tickets", "ticket_create"):
                self.assertEqual(self.client.get(self.url(name, "SCV")).status_code, 200, (user, name))
        self.client.force_login(self.staff)
        for name in ("client_list", "project_list", "team"):
            self.assertEqual(self.client.get(self.url(name)).status_code, 200)
        self.assertEqual(self.client.get(self.url("milestone_create", "SCV")).status_code, 200)


@override_settings(MEDIA_ROOT=MEDIA, LANGUAGE_CODE="en")
class BoardTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        wws = Company.objects.create(name="WWS")
        cls.staff = User.objects.create_user("staff", password="x", role=User.Role.STAFF)
        cls.client_user = User.objects.create_user("client", password="x", company=wws)
        cls.project = Project.objects.create(company=wws, name="Smart CV", key="SCV")
        cls.project.members.add(cls.client_user)
        cls.ticket = Ticket.objects.create(project=cls.project, title="Test me", author=cls.client_user,
                                           status=Ticket.Status.IN_TEST)
        Ticket.objects.create(project=cls.project, title="Secret task", author=cls.staff,
                              visibility=Ticket.Visibility.INTERNAL)

    def test_client_board_is_simple_and_read_only(self):
        self.client.force_login(self.client_user)
        response = self.client.get(reverse("project_board", args=["SCV"]))
        self.assertContains(response, "Your turn")
        self.assertContains(response, "Test me")
        self.assertNotContains(response, "Secret task")
        self.assertContains(response, "What we need from you")
        # Only the card waiting for the client can be moved by the client.
        self.assertContains(response, 'data-client="1"', count=1)
        move = self.client.post(reverse("ticket_move", args=[self.ticket.pk]), '{"status": "done"}',
                                content_type="application/json")
        self.assertEqual(move.status_code, 403)

    def action(self, ticket, **payload):
        return self.client.post(reverse("ticket_client_action", args=[ticket.pk]), json.dumps(payload),
                                content_type="application/json")

    def test_client_validates_or_refuses_a_test(self):
        self.client.force_login(self.client_user)
        self.assertEqual(self.action(self.ticket, action="test_ok").status_code, 200)
        self.ticket.refresh_from_db()
        self.assertEqual(self.ticket.status, "done")
        other = Ticket.objects.create(project=self.project, title="t2", author=self.staff, status="in_test")
        self.action(other, column="in_progress", message="Still broken on mobile")
        other.refresh_from_db()
        self.assertEqual(other.status, "in_progress")
        self.assertIn("Still broken on mobile", other.comments.get().body)

    def test_not_ok_requires_an_explanation(self):
        self.client.force_login(self.client_user)
        for payload in ({"action": "test_ko"}, {"column": "in_progress"}, {"action": "test_ko", "message": "  bad  "}):
            response = self.action(self.ticket, **payload)
            self.assertEqual(response.status_code, 400)
            self.assertTrue(response.json()["needs_message"])
        self.ticket.refresh_from_db()
        self.assertEqual(self.ticket.status, "in_test")
        self.assertFalse(self.ticket.comments.exists())

    def test_client_can_reopen_a_validated_ticket_with_explanation(self):
        self.client.force_login(self.client_user)
        self.action(self.ticket, action="test_ok")
        self.assertEqual(self.action(self.ticket, action="reopen").status_code, 400)
        self.action(self.ticket, action="reopen", message="The export is empty in Firefox")
        self.ticket.refresh_from_db()
        self.assertEqual(self.ticket.status, "in_progress")
        self.assertIsNone(self.ticket.closed_at)
        self.assertIn("Firefox", self.ticket.comments.get().body)

    def test_client_answers_question_but_cannot_move_other_cards(self):
        self.client.force_login(self.client_user)
        question = Ticket.objects.create(project=self.project, title="Q", author=self.staff, status="waiting_client")
        self.assertEqual(self.action(question, column="done").status_code, 400)
        self.action(question, action="answered")
        question.refresh_from_db()
        self.assertEqual(question.status, "to_analyse")
        self.assertTrue(question.events.filter(user=self.client_user, field="status").exists())
        busy = Ticket.objects.create(project=self.project, title="B", author=self.staff, status="in_progress")
        self.assertEqual(self.action(busy, action="test_ok").status_code, 400)
        secret = Ticket.objects.get(title="Secret task")
        secret.status = "in_test"
        secret.save()
        self.assertEqual(self.action(secret, action="test_ok").status_code, 404)

    def test_staff_moves_ticket_and_history_is_recorded(self):
        self.client.force_login(self.staff)
        response = self.client.post(reverse("ticket_move", args=[self.ticket.pk]), '{"status": "done"}',
                                    content_type="application/json")
        self.assertEqual(response.json()["status"], "done")
        self.ticket.refresh_from_db()
        self.assertEqual(self.ticket.status, "done")
        self.assertIsNotNone(self.ticket.closed_at)
        self.assertTrue(self.ticket.events.filter(field="status", new_value="Done").exists())
        bad = self.client.post(reverse("ticket_move", args=[self.ticket.pk]), '{"status": "nope"}',
                               content_type="application/json")
        self.assertEqual(bad.status_code, 400)

    def test_staff_boards_render_with_groups(self):
        self.client.force_login(self.staff)
        for group in ("", "project", "assignee", "priority", "type"):
            response = self.client.get(reverse("global_board"), {"group": group})
            self.assertContains(response, "Secret task")
        response = self.client.get(reverse("project_board", args=["SCV"]), {"group": "assignee", "q": "Test"})
        self.assertContains(response, "Test me")
        self.assertContains(response, 'draggable="true"')


@override_settings(MEDIA_ROOT=MEDIA, LANGUAGE_CODE="en", ORBIT_BASE_URL="https://orbit.example")
class NotificationTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        wws = Company.objects.create(name="WWS")
        cls.dev = User.objects.create_user("dev", email="dev@digitalia.fr", password="x", role=User.Role.STAFF)
        cls.lead = User.objects.create_user("lead", email="lead@digitalia.fr", password="x", role=User.Role.STAFF)
        cls.client_user = User.objects.create_user("client", email="julie@wws.fr", password="x", company=wws)
        cls.project = Project.objects.create(company=wws, name="Smart CV", key="SCV", lead=cls.lead)
        cls.project.members.add(cls.client_user)

    def test_client_is_told_when_it_is_their_turn(self):
        from django.core import mail
        ticket = Ticket.objects.create(project=self.project, title="Export", author=self.client_user, assignee=self.dev)
        self.client.force_login(self.dev)
        with self.captureOnCommitCallbacks(execute=True):
            self.client.post(reverse("ticket_move", args=[ticket.pk]), '{"status": "in_test"}', content_type="application/json")
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ["julie@wws.fr"])
        self.assertIn("SCV-1", mail.outbox[0].subject)
        self.assertIn("https://orbit.example/p/SCV/tickets/1/", mail.outbox[0].body)

    def test_assignee_gets_the_not_ok_explanation(self):
        from django.core import mail
        ticket = Ticket.objects.create(project=self.project, title="Export", author=self.dev, assignee=self.dev,
                                       status=Ticket.Status.IN_TEST)
        self.client.force_login(self.client_user)
        with self.captureOnCommitCallbacks(execute=True):
            self.client.post(reverse("ticket_client_action", args=[ticket.pk]),
                             '{"action": "test_ko", "message": "Nothing happens on click"}', content_type="application/json")
        self.assertEqual(mail.outbox[0].to, ["dev@digitalia.fr"])
        self.assertIn("Nothing happens on click", mail.outbox[0].body)

    def test_new_client_request_goes_to_the_project_lead_and_internal_stays_silent(self):
        from django.core import mail
        self.client.force_login(self.client_user)
        with self.captureOnCommitCallbacks(execute=True):
            self.client.post(reverse("ticket_create", args=["SCV"]),
                             {"type": "bug", "title": "Crash", "description": "It crashes", "priority": "high"})
        self.assertEqual(mail.outbox[0].to, ["lead@digitalia.fr"])
        mail.outbox.clear()
        internal = Ticket.objects.create(project=self.project, title="Refactor", author=self.dev,
                                         visibility=Ticket.Visibility.INTERNAL)
        self.client.force_login(self.dev)
        with self.captureOnCommitCallbacks(execute=True):
            self.client.post(reverse("ticket_move", args=[internal.pk]), '{"status": "in_test"}', content_type="application/json")
        self.assertEqual(mail.outbox, [])


@override_settings(MEDIA_ROOT=MEDIA, LANGUAGE_CODE="en")
class MediaTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        wws = Company.objects.create(name="WWS")
        cls.staff = User.objects.create_user("staff", password="x", role=User.Role.STAFF)
        cls.client_user = User.objects.create_user("client", password="x", company=wws)
        cls.project = Project.objects.create(company=wws, name="Smart CV", key="SCV")
        cls.project.members.add(cls.client_user)

    def test_photos_videos_audio_and_documents_are_accepted(self):
        self.client.force_login(self.client_user)
        files = [SimpleUploadedFile(n, b"x", content_type=t) for n, t in [
            ("photo.jpg", "image/jpeg"), ("screen.mp4", "video/mp4"), ("Note vocale.weba", "audio/webm"),
            ("spec.pdf", "application/pdf"), ("devis.xlsx", "application/octet-stream")]]
        self.client.post(reverse("ticket_create", args=["SCV"]),
                         {"type": "bug", "title": "Crash", "description": "d", "priority": "normal", "files": files})
        ticket = Ticket.objects.get()
        kinds = sorted(a.kind for a in ticket.attachments.all())
        self.assertEqual(kinds, ["audio", "document", "document", "image", "video"])
        page = self.client.get(ticket.get_absolute_url()).content.decode()
        self.assertIn("<video", page)
        self.assertIn("<audio", page)
        video = ticket.attachments.get(name="screen.mp4")
        response = self.client.get(reverse("attachment_download", args=[video.pk]))
        self.assertNotIn("attachment;", response.get("Content-Disposition", ""))

    def test_dangerous_files_are_refused(self):
        self.client.force_login(self.client_user)
        response = self.client.post(reverse("ticket_create", args=["SCV"]), {
            "type": "bug", "title": "x", "description": "d", "priority": "normal",
            "files": [SimpleUploadedFile("virus.exe", b"MZ")]})
        self.assertContains(response, "not accepted")
        self.assertFalse(Ticket.objects.exists())

    def test_not_ok_can_carry_a_voice_note(self):
        ticket = Ticket.objects.create(project=self.project, title="t", author=self.staff, status="in_test")
        self.client.force_login(self.client_user)
        self.client.post(reverse("ticket_client_action", args=[ticket.pk]), {
            "action": "test_ko", "message": "Voir ma note vocale et la capture",
            "files": [SimpleUploadedFile("note.weba", b"a"), SimpleUploadedFile("capture.png", b"p")]})
        ticket.refresh_from_db()
        self.assertEqual(ticket.status, "in_progress")
        comment = ticket.comments.get()
        self.assertEqual(sorted(a.kind for a in comment.attachments.all()), ["audio", "image"])
