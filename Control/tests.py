from datetime import date
from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from Attendance.geo import haversine_m
from Control.models import Role, UserProfile
from HR.models import Employee, OnboardingTask
from HR.services import create_employee
from Performance.models import TVDisplay
from Performance.services import employee_score


def make_user(name, role=None, superuser=False):
    user = User.objects.create_user(name, password="pw-12345-x", is_superuser=superuser, is_staff=superuser)
    if role:
        profile, _ = UserProfile.objects.get_or_create(user=user)
        profile.role = Role.objects.get(name=role)
        profile.save()
    Employee.objects.get_or_create(user=user, defaults={"status": "active"})
    return User.objects.get(pk=user.pk)


class SmokeTests(TestCase):
    PAGES = ["home", "profile", "leadplus_dashboard", "leads", "lead_create", "pipeline", "tasks",
             "my_onboarding", "attendance", "performance", "performance_me"]
    HR_PAGES = ["hr_employees", "hr_employee_create", "hr_onboarding", "attendance_dashboard",
                "attendance_monthly", "attendance_offices", "performance_kpis", "performance_tv_manage"]

    def test_director_sees_every_page(self):
        user = make_user("boss", superuser=True)
        self.client.force_login(user)
        for name in self.PAGES + self.HR_PAGES:
            response = self.client.get(reverse(name))
            self.assertEqual(response.status_code, 200, name)
        emp = user.employee
        for name in ["hr_employee_detail", "performance_employee", "performance_entries"]:
            self.assertEqual(self.client.get(reverse(name, args=[emp.pk])).status_code, 200, name)

    def test_employee_blocked_from_hr_and_crm(self):
        user = make_user("dev", role="developer")
        self.client.force_login(user)
        for name in ["hr_employees", "attendance_dashboard", "performance_kpis", "leads"]:
            self.assertEqual(self.client.get(reverse(name)).status_code, 403, name)
        self.assertEqual(self.client.get(reverse("attendance")).status_code, 200)

    def test_anonymous_redirected(self):
        self.assertEqual(self.client.get(reverse("home")).status_code, 302)

    def test_onboarding_auto_activates(self):
        employee, password = create_employee(
            username="ann", first_name="Ann", last_name="Lee", email="ann@example.com", designation="SEO", role_name="developer")
        self.assertTrue(password)
        self.assertEqual(employee.status, "onboarding")
        for task in employee.onboarding_tasks.filter(required=True):
            task.status = "done"
            task.save()
        employee.refresh_from_db()
        self.assertEqual(employee.status, "active")

    def test_haversine(self):
        self.assertAlmostEqual(haversine_m(0, 0, 0, 1), 111195, delta=200)
        self.assertEqual(haversine_m(10, 10, 10, 10), 0)

    def test_score_without_data(self):
        user = make_user("x", role="developer")
        self.assertIn("score", employee_score(user.employee, date.today().replace(day=1)))

    def test_tv_token(self):
        make_user("tvuser", role="developer")
        display = TVDisplay.objects.create(name="Lobby")
        ok = self.client.get(reverse("tv_data", args=[display.token]))
        self.assertEqual(ok.status_code, 200)
        self.assertIn("no-store", ok["Cache-Control"])
        self.assertEqual(self.client.get(reverse("tv_page", args=[display.token])).status_code, 200)
        self.assertEqual(self.client.get(reverse("tv_data", args=["bogus"])).status_code, 404)

class HierarchyTests(TestCase):
    def test_access_by_role(self):
        expected = {
            "management": {"hr_employees": 200, "leads": 200, "performance_kpis": 200},
            "hr": {"hr_employees": 200, "leads": 403},
            "project_manager": {"hr_employees": 403, "leads": 200},
            "bd_executive": {"hr_employees": 403, "leads": 200, "performance_kpis": 403},
            "graphic_designer": {"hr_employees": 403, "leads": 403, "attendance": 200},
        }
        for role, pages in expected.items():
            user = make_user(f"u_{role}", role=role)
            self.client.force_login(user)
            for name, status in pages.items():
                self.assertEqual(self.client.get(reverse(name)).status_code, status, f"{role}:{name}")

    def test_hr_cannot_grant_privileged_roles(self):
        from Control.permissions import assignable_roles
        names = set(assignable_roles(make_user("h", role="hr")).values_list("name", flat=True))
        self.assertNotIn("super_admin", names)
        self.assertNotIn("management", names)
        self.assertIn("developer", names)
        admin_names = set(assignable_roles(make_user("a", role="super_admin")).values_list("name", flat=True))
        self.assertIn("super_admin", admin_names)

    def test_super_admin_role_grants_superuser(self):
        user = make_user("s", role="super_admin")
        user.refresh_from_db()
        self.assertTrue(user.is_superuser)

    def test_team_lead_sees_team_leads(self):
        from LeadManager.models import Lead
        from LeadManager.views import scoped_leads
        lead_user = make_user("tl", role="bd_team_lead")
        member = make_user("ex", role="bd_executive")
        member.employee.manager = lead_user.employee
        member.employee.save()
        other = make_user("ex2", role="bd_executive")
        mine = Lead.objects.create(name="A", owner=member)
        Lead.objects.create(name="B", owner=other)
        self.assertEqual(list(scoped_leads(lead_user)), [mine])


class CustomRoleAndWorkflowTests(TestCase):
    def test_super_admin_defines_role_and_it_takes_effect(self):
        admin = make_user("root", role="super_admin")
        self.client.force_login(admin)
        response = self.client.post(reverse("role_create"), {
            "label": "SEO Analyst", "description": "", "level": 8, "is_active": "on", "can_use_crm": "on",
        })
        self.assertEqual(response.status_code, 302)
        role = Role.objects.get(name="seo_analyst")
        self.assertTrue(role.can_use_crm)
        self.assertFalse(role.can_manage_hr)
        analyst = make_user("seo", role="seo_analyst")
        self.client.force_login(analyst)
        self.assertEqual(self.client.get(reverse("leads")).status_code, 200)
        self.assertEqual(self.client.get(reverse("hr_employees")).status_code, 403)
        self.assertEqual(self.client.get(reverse("roles")).status_code, 403)

    def test_only_super_admin_manages_roles_and_workflows(self):
        for role in ("hr", "management"):
            self.client.force_login(make_user(f"x_{role}", role=role))
            for name in ("roles", "role_create", "hr_workflows", "hr_workflow_create"):
                self.assertEqual(self.client.get(reverse(name)).status_code, 403, f"{role}:{name}")
        self.client.force_login(make_user("sa", role="super_admin"))
        for name in ("roles", "role_create", "hr_workflows", "hr_workflow_create"):
            self.assertEqual(self.client.get(reverse(name)).status_code, 200, name)

    def test_system_role_protected(self):
        self.client.force_login(make_user("sa2", role="super_admin"))
        role = Role.objects.get(name="super_admin")
        self.client.post(reverse("role_delete", args=[role.pk]))
        self.assertTrue(Role.objects.filter(name="super_admin").exists())

    def test_delete_role_reassigns_users(self):
        self.client.force_login(make_user("sa3", role="super_admin"))
        victim = make_user("vic", role="developer")
        role = Role.objects.get(name="developer")
        target = Role.objects.get(name="videographer")
        self.assertEqual(self.client.get(reverse("role_detail", args=[role.pk])).status_code, 200)
        self.client.post(reverse("role_delete", args=[role.pk]))
        self.assertTrue(Role.objects.filter(pk=role.pk).exists())
        self.client.post(reverse("role_delete", args=[role.pk]), {"reassign_to": target.pk})
        self.assertFalse(Role.objects.filter(pk=role.pk).exists())
        victim.profile.refresh_from_db()
        self.assertEqual(victim.profile.role, target)

    def test_role_specific_workflow_with_approval(self):
        from HR.models import OnboardingTemplate, OnboardingTemplateTask
        role = Role.objects.get(name="video_editor")
        template = OnboardingTemplate.objects.create(name="Editors", role=role)
        OnboardingTemplateTask.objects.create(
            template=template, title="Submit showreel", requires_approval=True, approver="hr")
        employee, _ = create_employee(
            username="ed", first_name="Ed", last_name="It", email="e@example.com", role_name="video_editor")
        task = employee.onboarding_tasks.get()
        self.assertEqual(task.title, "Submit showreel")
        self.assertEqual(task.complete(employee.user), "submitted")
        employee.refresh_from_db()
        self.assertEqual(employee.status, "onboarding")
        self.assertFalse(task.can_approve(employee.user))
        hr = make_user("hrx", role="hr")
        self.client.force_login(hr)
        self.client.post(reverse("hr_task_update", args=[task.pk]), {"action": "approve"})
        task.refresh_from_db()
        self.assertEqual(task.status, "done")
        employee.refresh_from_db()
        self.assertEqual(employee.status, "active")

    def test_workflow_editor_saves_steps(self):
        from HR.models import OnboardingTemplate
        self.client.force_login(make_user("sa3", role="super_admin"))
        data = {"name": "Dev flow", "is_active": "on",
                "tasks-TOTAL_FORMS": "1", "tasks-INITIAL_FORMS": "0", "tasks-MIN_NUM_FORMS": "0",
                "tasks-MAX_NUM_FORMS": "1000", "tasks-0-title": "Set up repo access", "tasks-0-category": "setup",
                "tasks-0-responsible": "it", "tasks-0-due_after_days": "1", "tasks-0-approver": "hr",
                "tasks-0-order": "1", "tasks-0-required": "on"}
        self.client.post(reverse("hr_workflow_create"), data)
        self.assertEqual(OnboardingTemplate.objects.get(name="Dev flow").tasks.count(), 1)


class ImprovementPlanTests(TestCase):
    def test_pip_lifecycle_and_access(self):
        from Performance.models import ImprovementPlan
        hr = make_user("hr1", role="hr")
        dev = make_user("dev1", role="developer")
        emp = create_employee(username="pipemp", password="Str0ng!pass99", first_name="P", last_name="E",
                              email="p@e.com", role_name="developer", date_of_joining=date.today()) if False else dev.employee
        self.client.force_login(dev)
        self.assertEqual(self.client.get(reverse("pip_list")).status_code, 403)
        self.client.force_login(hr)
        self.assertEqual(self.client.get(reverse("pip_list")).status_code, 200)
        self.assertEqual(self.client.get(reverse("pip_create") + f"?employee={emp.pk}").status_code, 200)
        r = self.client.post(reverse("pip_create"), {
            "employee": emp.pk, "reason": "Missed targets", "goals": "Hit 60", "start_date": "2026-10-01",
            "review_date": "2026-10-31", "target_score": 60, "duration_days": 60})
        plan = ImprovementPlan.objects.get()
        self.assertRedirects(r, reverse("pip_detail", args=[plan.pk]))
        self.client.post(reverse("pip_update", args=[plan.pk]), {"note": "Week 1 ok", "score": "55"})
        self.assertEqual(plan.updates.count(), 1)
        self.client.post(reverse("pip_close", args=[plan.pk]), {"action": "improved", "outcome": "Good"})
        plan.refresh_from_db()
        self.assertEqual(plan.status, "improved")
        self.client.post(reverse("pip_delete", args=[plan.pk]))
        self.assertFalse(ImprovementPlan.objects.exists())
