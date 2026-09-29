import datetime
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
        self.assertNotContains(response, 'draggable="true"')
        move = self.client.post(reverse("ticket_move", args=[self.ticket.pk]), '{"status": "done"}',
                                content_type="application/json")
        self.assertEqual(move.status_code, 403)

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
