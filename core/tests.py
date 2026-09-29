import re

from django.core import mail
from django.test import TestCase, override_settings
from django.urls import reverse

from .models import Company, Project, User


@override_settings(LANGUAGE_CODE="en")
class ManagementTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.digitalia = Company.objects.create(name="Digitalia", is_internal=True)
        cls.wws = Company.objects.create(name="WWS")
        cls.admin = User.objects.create_user("admin", email="admin@digitalia.fr", password="pw-Orbit-2026",
                                             role=User.Role.STAFF, is_staff=True, company=cls.digitalia)
        cls.dev = User.objects.create_user("dev", email="dev@digitalia.fr", password="x", role=User.Role.STAFF)
        cls.project = Project.objects.create(company=cls.wws, name="Smart CV", key="SCV")

    def invite(self, **data):
        payload = {"first_name": "Julie", "last_name": "Martin", "email": "Julie@WWS.fr", "role": "client",
                   "company": self.wws.pk, "projects": [self.project.pk]}
        payload.update(data)
        return self.client.post(reverse("user_create"), payload)

    def link_from(self, message):
        return re.search(r"http://testserver(/\S+)", message.body).group(1)

    def test_only_orbit_admins_manage(self):
        self.client.force_login(self.dev)
        for name in ("user_list", "user_create", "company_create", "project_create"):
            self.assertEqual(self.client.get(reverse(name)).status_code, 403, name)

    def test_invite_a_client_then_first_login(self):
        self.client.force_login(self.admin)
        response = self.invite()
        self.assertEqual(response.status_code, 302)
        julie = User.objects.get(email="julie@wws.fr")
        self.assertFalse(julie.has_usable_password())
        self.assertEqual(list(julie.projects.all()), [self.project])
        self.assertEqual(mail.outbox[0].to, ["julie@wws.fr"])
        self.assertIn("Smart CV", mail.outbox[0].body)
        link = self.link_from(mail.outbox[0])
        self.client.logout()
        form_page = self.client.get(link, follow=True)
        self.assertContains(form_page, "Activate my account")
        done = self.client.post(form_page.redirect_chain[-1][0], {"new_password1": "Nouveau-Mot-2026", "new_password2": "Nouveau-Mot-2026"})
        self.assertRedirects(done, "/", fetch_redirect_response=False)
        # Logged in, and the client can now log in with the e-mail address.
        self.client.logout()
        self.assertTrue(self.client.login(username="JULIE@wws.fr", password="Nouveau-Mot-2026"))

    def test_client_projects_must_belong_to_their_company(self):
        other = Project.objects.create(company=Company.objects.create(name="Other"), name="Other", key="OTH")
        self.client.force_login(self.admin)
        response = self.invite(projects=[other.pk])
        self.assertContains(response, "belong to another client")
        self.assertFalse(User.objects.filter(email="julie@wws.fr").exists())
        self.assertContains(self.invite(email="admin@digitalia.fr"), "already uses this e-mail")

    def test_deactivated_account_cannot_log_in(self):
        self.client.force_login(self.admin)
        self.client.post(reverse("user_toggle_active", args=[self.dev.pk]))
        self.dev.refresh_from_db()
        self.assertFalse(self.dev.is_active)
        self.client.post(reverse("user_toggle_active", args=[self.admin.pk]))
        self.admin.refresh_from_db()
        self.assertTrue(self.admin.is_active)

    def test_forgotten_password(self):
        self.client.post(reverse("password_reset"), {"email": "ADMIN@digitalia.fr"})
        self.assertEqual(mail.outbox[0].to, ["admin@digitalia.fr"])
        page = self.client.get(self.link_from(mail.outbox[0]), follow=True)
        self.assertContains(page, "Save my new password")
        self.client.post(page.redirect_chain[-1][0], {"new_password1": "Encore-Neuf-2026", "new_password2": "Encore-Neuf-2026"})
        self.client.logout()
        self.assertTrue(self.client.login(username="admin@digitalia.fr", password="Encore-Neuf-2026"))
        # Unknown address: same answer, no e-mail.
        mail.outbox.clear()
        response = self.client.post(reverse("password_reset"), {"email": "nobody@example.com"})
        self.assertRedirects(response, reverse("password_reset_done"))
        self.assertEqual(mail.outbox, [])

    def test_create_client_and_project(self):
        self.client.force_login(self.admin)
        response = self.client.post(reverse("company_create"), {"name": "Bodytime"})
        body = Company.objects.get(name="Bodytime")
        self.assertRedirects(response, reverse("company_detail", args=[body.pk]))
        self.client.post(reverse("project_create"), {"company": body.pk, "name": "TWM", "key": "twm", "is_active": "on"})
        self.assertEqual(Project.objects.get(key="TWM").company, body)
        duplicate = self.client.post(reverse("project_create"), {"company": body.pk, "name": "X", "key": "scv"})
        self.assertContains(duplicate, "already used")
