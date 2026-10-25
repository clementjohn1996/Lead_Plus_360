import io
import shutil
import tempfile

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from PIL import Image

from HR.models import Employee, OnboardingTask
from HR.services import create_employee
from LeadManager.models import Department
from Performance.models import KPI
from Performance.services import applicable_kpis

from .test_helpers import make_user


def png_bytes():
    buf = io.BytesIO()
    Image.new("RGB", (8, 8), "purple").save(buf, "PNG")
    return buf.getvalue()


class NavigationAndGuideTests(TestCase):
    def test_developer_never_sees_admin_or_crm_entries(self):
        dev = make_user("dev1", role="developer")
        self.client.force_login(dev)
        html = self.client.get(reverse("home")).content.decode()
        for hidden in ("Control center", "Roles &amp; access", "Growth overview", "Add lead", "Accounts overview"):
            self.assertNotIn(hidden, html)
        self.assertIn("My onboarding", html)

    def test_guide_is_role_specific(self):
        self.client.force_login(make_user("dev2", role="developer"))
        html = self.client.get(reverse("guide")).content.decode()
        self.assertNotIn("Super Admin — Configuration", html)
        self.assertNotIn("TV Displays", html)
        self.assertIn("Profile, photo", html)
        self.client.force_login(make_user("adm1", role="super_admin"))
        html = self.client.get(reverse("guide")).content.decode()
        self.assertIn("Super Admin — Configuration", html)
        self.assertIn("Growth engine", html)

    def test_no_add_lead_button_in_every_header(self):
        self.client.force_login(make_user("sales1", role="bd_executive"))
        html = self.client.get(reverse("performance_me")).content.decode()
        self.assertNotIn("+ Add lead", html)

    def test_outreach_requires_permission(self):
        self.client.force_login(make_user("dev3", role="developer"))
        self.assertEqual(self.client.get(reverse("outreach_dashboard")).status_code, 403)
        self.client.force_login(make_user("sales2", role="bd_executive"))
        self.assertEqual(self.client.get(reverse("outreach_dashboard")).status_code, 200)

    def test_all_outreach_pages_render_for_admin(self):
        self.client.force_login(make_user("adm2", role="super_admin", superuser=True))
        for name in ("outreach_dashboard", "outreach_prospects", "outreach_prospect_new", "outreach_import",
                     "outreach_cohorts", "outreach_campaigns", "outreach_campaign_new", "outreach_outbox",
                     "outreach_settings", "outreach_export", "hr_departments", "roles", "control_center"):
            self.assertEqual(self.client.get(reverse(name)).status_code, 200, name)


class KpiDepartmentTests(TestCase):
    def test_kpi_applies_to_every_ticked_department(self):
        d1, d2, d3 = (Department.objects.create(name=n) for n in ("Alpha", "Beta", "Gamma"))
        kpi = KPI.objects.create(name="Shared KPI", weight=5)
        kpi.departments.set([d1, d2])
        for dept, expected in ((d1, True), (d2, True), (d3, False)):
            emp = create_employee(username=f"u{dept.pk}", first_name="A", last_name="B", email="a@b.co",
                                  role_name="developer", department=dept)[0]
            self.assertEqual(kpi in applicable_kpis(emp), expected)


class OnboardingChainTests(TestCase):
    def _task(self, **kw):
        emp = create_employee(username="newbie", first_name="N", last_name="B", email="n@b.co", role_name="developer")[0]
        emp.onboarding_tasks.all().delete()
        task = OnboardingTask.objects.create(
            employee=emp, title="Education: Graduation certificate", category="documents", responsible="employee",
            requires_approval=True, approver="hr_manager", verifier="hr_recruiter", skippable=True, **kw)
        return emp, task

    def test_recruiter_verifies_then_hr_manager_confirms(self):
        emp, task = self._task()
        self.assertEqual(task.complete(emp.user), "submitted")
        recruiter = make_user("rec", role="hr_recruiter")
        manager = make_user("hrm", role="hr")
        self.client.force_login(recruiter)
        self.client.post(reverse("hr_task_update", args=[task.pk]), {"action": "verify"})
        task.refresh_from_db()
        self.assertEqual(task.status, "verified")
        self.assertEqual(self.client.post(reverse("hr_task_update", args=[task.pk]), {"action": "approve"}).status_code, 403)
        self.client.force_login(manager)
        self.client.post(reverse("hr_task_update", args=[task.pk]), {"action": "approve"})
        task.refresh_from_db()
        self.assertEqual(task.status, "done")

    def test_employee_cannot_verify_own_task(self):
        emp, task = self._task()
        task.complete(emp.user)
        self.client.force_login(emp.user)
        self.assertEqual(self.client.post(reverse("hr_task_update", args=[task.pk]), {"action": "verify"}).status_code, 403)

    def test_employee_can_skip_a_skippable_step(self):
        emp, task = self._task()
        self.client.force_login(emp.user)
        self.client.post(reverse("hr_task_update", args=[task.pk]), {"action": "skip_self"})
        task.refresh_from_db()
        self.assertEqual(task.status, "skipped")

    def test_fresher_experience_steps_are_skipped(self):
        emp = create_employee(username="fresh", first_name="F", last_name="R", email="f@r.co",
                              role_name="developer", is_fresher=True)[0]
        exp = emp.onboarding_tasks.filter(title__startswith="Experience:")
        self.assertTrue(exp.exists())
        self.assertFalse(exp.exclude(status="skipped").exists())
        edu = emp.onboarding_tasks.filter(title__startswith="Education:")
        self.assertEqual(edu.count(), 4)
        self.assertFalse(edu.filter(status="skipped").exists())


class PhotoTests(TestCase):
    def test_hr_can_add_photo_and_it_shows_in_list(self):
        media = tempfile.mkdtemp()
        try:
            with override_settings(MEDIA_ROOT=media):
                hr = make_user("hrp", role="hr")
                emp = create_employee(username="pic", first_name="P", last_name="C", email="p@c.co", role_name="developer")[0]
                self.client.force_login(hr)
                upload = SimpleUploadedFile("me.png", png_bytes(), content_type="image/png")
                self.client.post(reverse("hr_employee_photo", args=[emp.pk]), {"photo": upload})
                emp = Employee.objects.get(pk=emp.pk)
                self.assertTrue(emp.photo_url)
                self.assertIn("<img", self.client.get(reverse("hr_employees")).content.decode())
        finally:
            shutil.rmtree(media, ignore_errors=True)
