from datetime import date, datetime, time, timedelta
from decimal import Decimal

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from Control.models import Role, UserProfile
from HR.models import Employee
from Delivery.calendar_models import DeliveryPackage, PackageTaskTemplate, DeliveryPlan, DeliveryCalendarTask
from LeadManager.models import Department, Lead, LeadSource, Service, Deal, Activity, FollowUpSchedule
from Performance import bde
from Performance.models import (
    Appraisal,
    BDEConfig,
    BDETarget,
    ImprovementPlan,
    ImprovementUpdate,
    MonthlyPerformance,
    PerformanceAlert,
    PerformanceAudit,
    TVDisplay,
    TVPoster,
)


PASSWORD = "1234"
DEMO_PREFIX = "demo_"
DEMO_EMPLOYEES = [
    ("demo_arun", "Arun", "Nair", "arun@example.com", "green", "bd_executive"),
    ("demo_meera", "Meera", "Joseph", "meera@example.com", "pip_red", "bd_executive"),
    ("demo_rohit", "Rohit", "Kumar", "rohit@example.com", "pip_yellow", "bd_executive"),
    ("demo_sneha", "Sneha", "Thomas", "sneha@example.com", "appraisal", "bd_executive"),
    ("demo_alan", "Alan", "George", "alan@example.com", "neutral", "bd_executive"),
    ("demo_divya", "Divya", "Menon", "divya@example.com", "green", "bd_executive"),
]

DEMO_TEAM_MEMBERS = [
    ("demo_priya", "Priya", "Sharma", "priya@example.com", "Web Developer", "developer"),
    ("demo_kamal", "Kamal", "Pillai", "kamal@example.com", "Graphic Designer", "graphic_designer"),
    ("demo_riya", "Riya", "Varma", "riya@example.com", "Video Editor", "video_editor"),
    ("demo_noor", "Noor", "Khan", "noor@example.com", "Videographer", "videographer"),
    ("demo_imran", "Imran", "Sheikh", "imran@example.com", "Digital Marketer", "digital_marketing"),
]

# June -> October 2026. October is the current (partial) month; September is the last completed.
PATTERNS = {
    "green": ["green", "green", "green", "green", "green"],
    "pip_red": ["green", "green", "red", "red", "red"],
    "pip_yellow": ["yellow", "yellow", "yellow", "yellow", "yellow"],
    "appraisal": ["green", "green", "green", "yellow", "green"],
    "neutral": ["red", "yellow", "red", "yellow", "yellow"],
}
REVENUE_BY_COLOUR = {"red": Decimal("80000"), "yellow": Decimal("120000"), "green": Decimal("180000")}


class Command(BaseCommand):
    help = "Create/update deterministic LeadPlus360 demo data. Demo users use password 1234."

    def add_arguments(self, parser):
        parser.add_argument(
            "--fresh-demo",
            action="store_true",
            help="Delete previously seeded demo records before recreating them.",
        )

    def role(self, name, label, **flags):
        defaults = {
            "label": label,
            "description": "Demo role created by seed_demo_data.",
            "is_active": True,
            "is_system": True,
        }
        defaults.update(flags)
        role, _ = Role.objects.update_or_create(name=name, defaults=defaults)
        return role

    def upsert_user(self, username, first, last, email, role_name, staff=False, superuser=False):
        role = Role.objects.get(name=role_name)
        user, _ = User.objects.get_or_create(username=username, defaults={"email": email})
        user.first_name = first
        user.last_name = last
        user.email = email
        user.is_active = True
        user.is_staff = staff or superuser
        user.is_superuser = superuser
        user.set_password(PASSWORD)
        user.save()
        profile, _ = UserProfile.objects.get_or_create(user=user)
        profile.role = role
        profile.phone = "9999900000"
        profile.save()
        return user

    def employee(self, user, department, manager=None, dob=None):
        emp, _ = Employee.objects.get_or_create(user=user)
        emp.department = department
        emp.designation = "Business Development Executive"
        emp.manager = manager
        emp.employment_type = "full_time"
        emp.work_mode = "office"
        emp.status = "active"
        emp.date_of_joining = date(2024, 1, 15)
        emp.date_of_birth = dob
        emp.personal_email = user.email
        emp.show_on_tv = True
        emp.save()
        return emp

    def source(self, name):
        return LeadSource.objects.get_or_create(name=name, defaults={"is_active": True})[0]

    def service(self, name, category, rate):
        service, _ = Service.objects.get_or_create(
            name=name,
            defaults={"category": category, "default_rate": rate, "is_active": True},
        )
        service.category = category
        service.default_rate = rate
        service.is_active = True
        service.save()
        return service

    def department(self, name, head=None):
        dep, _ = Department.objects.get_or_create(name=name)
        dep.head = head
        dep.save()
        return dep

    def set_stage_without_signal_noise(self, lead, stage, changed_by, changed_at):
        """Set a stage and create the historical stage transition used by revenue_for()."""
        Lead.objects.filter(pk=lead.pk).update(stage=stage)
        # The normal signal may already have created a history row. We explicitly
        # ensure a correctly dated Won history row exists for the demo month.
        from LeadManager.models import LeadStatusHistory
        history = LeadStatusHistory.objects.create(
            lead=lead,
            from_stage="proposal_sent" if stage == "won" else "new",
            to_stage=stage,
            changed_by=changed_by,
            reason="Demo data",
        )
        LeadStatusHistory.objects.filter(pk=history.pk).update(changed_at=changed_at)

    def add_won_revenue(self, employee, month, revenue, source, service, index):
        day = min(15 + index, 26)
        won_at = timezone.make_aware(datetime.combine(month, time(10, 0))) + timedelta(days=day - 1)
        name = f"Demo Client {employee.user.first_name} {month:%b} {index}"
        lead, _ = Lead.objects.get_or_create(
            name=name,
            owner=employee.user,
            defaults={
                "company": f"{employee.user.first_name} Demo Solutions {month:%m}",
                "designation": "Founder",
                "industry": "Technology",
                "email": f"{employee.user.username}.{month:%m}@example.com",
                "phone": f"98000{employee.pk:04d}",
                "country": "India",
                "state": "Kerala",
                "city": "Thiruvananthapuram",
                "source": source,
                "service": service,
                "stage": "won",
                "temperature": "hot",
                "priority": "high",
                "owner": employee.user,
                "manager": employee.manager.user if employee.manager else None,
                "estimated_value": revenue,
                "budget_tier": "medium",
                "billing_type": "onetime",
                "probability": 100,
                "notes": "Seeded LeadPlus360 demo record.",
            },
        )
        lead.source = source
        lead.service = service
        lead.stage = "won"
        lead.temperature = "hot"
        lead.priority = "high"
        lead.estimated_value = revenue
        lead.probability = 100
        lead.manager = employee.manager.user if employee.manager else None
        lead.save()
        lead.services.add(service)

        deal, _ = Deal.objects.update_or_create(
            lead=lead,
            defaults={
                "value": revenue,
                "service": service,
                "expected_close": month,
                "status": "won",
                "notes": "Seeded demo won deal.",
            },
        )

        from LeadManager.models import LeadStatusHistory
        history, _ = LeadStatusHistory.objects.get_or_create(
            lead=lead,
            to_stage="won",
            reason="Demo data",
            defaults={"from_stage": "proposal_sent", "changed_by": employee.user},
        )
        LeadStatusHistory.objects.filter(pk=history.pk).update(changed_at=won_at, changed_by=employee.user)

        Activity.objects.get_or_create(
            lead=lead,
            subject="Demo discovery call",
            defaults={
                "activity_type": "call",
                "outcome": "interested",
                "body": "Demo activity created for performance testing.",
                "created_by": employee.user,
            },
        )
        return lead, deal

    def add_pipeline_leads(self, employees, source, service):
        stages = ["new", "contacted", "in_followup", "proposal_sent", "negotiation", "lost"]
        for i, employee in enumerate(employees, 1):
            for j, stage in enumerate(stages, 1):
                lead, _ = Lead.objects.get_or_create(
                    name=f"Pipeline Prospect {i}-{j}",
                    owner=employee.user,
                    defaults={
                        "company": f"Prospect Company {i}-{j}",
                        "email": f"prospect{i}{j}@example.com",
                        "phone": f"97000{i:02d}{j:02d}",
                        "country": "India",
                        "state": "Kerala",
                        "city": "Kochi",
                        "source": source,
                        "service": service,
                        "stage": stage,
                        "temperature": "warm" if stage != "negotiation" else "hot",
                        "priority": "medium",
                        "owner": employee.user,
                        "manager": employee.manager.user if employee.manager else None,
                        "estimated_value": Decimal("150000") + (j * Decimal("10000")),
                        "probability": 50 if stage in {"proposal_sent", "negotiation"} else 20,
                        "notes": "Seeded demo pipeline prospect.",
                    },
                )
                lead.services.add(service)

    def create_delivery_plans(self, employees, team_members, manager_user, admin_user, today):
        """Create demo delivery plans with calendar tasks from won leads."""
        package = DeliveryPackage.objects.filter(name="Digital Marketing + Website + SEO").first()
        if not package:
            self.stdout.write(self.style.WARNING("  No demo delivery package found; skipping calendar plans."))
            return

        task_role_map = {
            "video": ("video", "videographer"),
            "poster": ("design", "graphic_designer"),
            "meta_ads": ("marketing", "digital_marketing"),
            "website": ("web", "developer"),
            "seo": ("seo", "digital_marketing"),
        }
        video_role_alternate = {"videographer": "video_editor", "video_editor": "videographer"}
        progress_for = {"completed": 100, "in_progress": 50, "review": 75, "planned": 0, "blocked": 0, "cancelled": 0}

        pattern_configs = {
            "green": ("approved", ["completed", "completed", "review", "in_progress", "planned"], -20),
            "appraisal": ("in_progress", ["in_progress", "completed", "in_progress", "planned", "planned"], -10),
            "pip_red": ("pending_approval", ["planned"] * 5, 5),
            "pip_yellow": ("draft", ["planned"] * 5, 15),
            "neutral": ("approved", ["completed", "in_progress", "review", "planned", "planned"], -5),
        }
        start_offsets = [-20, -10, 5, 15, 0, 15]
        plans = []
        for idx, (emp, pattern) in enumerate(employees):
            status, task_statuses, offset = pattern_configs.get(pattern, ("approved", ["in_progress"] * 5, 10))
            if idx < len(start_offsets):
                offset = start_offsets[idx]
            lead = Lead.objects.filter(owner=emp.user, stage="won").order_by("-id").first()
            if not lead:
                continue
            start = today + timedelta(days=offset)
            plan_defaults = {
                "package": package, "bde": emp.user, "bdm": manager_user,
                "start_date": start, "target_completion_date": start + timedelta(days=30),
                "status": status, "package_name": "Digital Marketing + Website + SEO",
                "bdm_notes": "Demo delivery plan." if status != "draft" else "",
                "submitted_at": timezone.make_aware(datetime.combine(start + timedelta(days=2), time(10, 0))) if status in ("pending_approval", "approved") else None,
                "approved_at": timezone.make_aware(datetime.combine(start + timedelta(days=3), time(10, 0))) if status == "approved" else None,
                "approved_by": manager_user if status == "approved" else None,
            }
            plan, _ = DeliveryPlan.objects.update_or_create(lead=lead, defaults=plan_defaults)
            plans.append(plan)

            cursor = start
            for tpl in package.task_templates.filter(active=True).order_by("sequence"):
                task_start = cursor
                due = task_start + timedelta(days=max(tpl.default_duration_days - 1, 0))
                task_status = task_statuses.pop(0) if task_statuses else "planned"
                role_assignment, team_role = task_role_map.get(tpl.task_type, ("other", None))
                if tpl.task_type == "video" and idx % 2 == 0 and team_role in video_role_alternate:
                    team_role = video_role_alternate[team_role]
                assigned = team_members.get(team_role) if team_role else None

                task_kwargs = {
                    "plan": plan, "template": tpl, "task_type": tpl.task_type,
                    "title": tpl.title, "icon": tpl.icon, "gif_url": tpl.gif_url,
                    "assignment_role": role_assignment,
                    "start_date": task_start, "due_date": due, "final_date": due,
                    "status": task_status, "progress": progress_for.get(task_status, 0),
                    "reminder_enabled": task_status in ("in_progress", "planned"),
                    "reminder_days_before": 1,
                }
                if tpl.task_type == "video":
                    task_kwargs["shoot_date"] = task_start
                    task_kwargs["draft_date"] = task_start + timedelta(days=max(tpl.default_duration_days // 2, 1))
                else:
                    task_kwargs["draft_date"] = task_start + timedelta(days=max(tpl.default_duration_days // 2, 1))
                    task_kwargs["launch_date"] = task_start + timedelta(days=max(tpl.default_duration_days // 2, 1))
                if assigned and assigned != emp.user:
                    task_kwargs["assigned_to"] = assigned

                DeliveryCalendarTask.objects.update_or_create(
                    plan=plan, template=tpl,
                    defaults=task_kwargs,
                )
                cursor = due + timedelta(days=1)

        if plans:
            self.stdout.write(f"  Created {len(plans)} delivery plan(s) with calendar tasks.")

    @transaction.atomic
    def handle(self, *args, **options):
        self.stdout.write(self.style.MIGRATE_HEADING("Seeding LeadPlus360 demo data..."))

        # Roles match the current Control migrations: bd_manager, bd_executive, super_admin.
        super_role = self.role(
            "super_admin", "Super Admin", level=1, can_use_crm=True, sees_all_leads=True,
            can_manage_team=True, can_manage_hr=True, is_privileged=True, is_super_admin=True,
        )
        manager_role = self.role(
            "bd_manager", "Business Development Manager", level=4, can_use_crm=True,
            sees_all_leads=True, can_manage_team=True,
        )
        exec_role = self.role("bd_executive", "Business Development Executive", level=6, can_use_crm=True)
        self.role("bd_team_lead", "BD Team Lead", level=8, can_use_crm=True, can_manage_team=True)
        self.role("developer", "Web Developer", level=50)
        self.role("graphic_designer", "Graphic Designer", level=52)
        self.role("videographer", "Videographer", level=52)
        self.role("video_editor", "Video Editor", level=52)
        self.role("digital_marketing", "Digital Marketing", level=52)

        admin_user = self.upsert_user(
            "demo_admin", "Demo", "Admin", "demo.admin@example.com", super_role.name, staff=True, superuser=True
        )
        manager_user = self.upsert_user(
            "demo_manager", "Demo", "Manager", "demo.manager@example.com", manager_role.name, staff=True
        )

        bd_department = self.department("Business Development", manager_user)
        services = [
            self.service("Website Development", "web_dev", Decimal("150000")),
            self.service("SEO & Growth", "seo", Decimal("75000")),
            self.service("Google Ads", "google_ads", Decimal("50000")),
            self.service("Social Media & Branding", "social_branding", Decimal("60000")),
        ]
        for service in services:
            bd_department.services.add(service)

        manager_profile = manager_user.profile
        employees = []
        for idx, (username, first, last, email, pattern, role_name) in enumerate(DEMO_EMPLOYEES):
            user = self.upsert_user(username, first, last, email, role_name)
            emp = self.employee(
                user,
                bd_department,
                manager=None,
                dob=date(1994 + (idx % 4), 1 + idx, 5 + idx),
            )
            employees.append((emp, pattern))

        manager_emp, _ = Employee.objects.get_or_create(user=manager_user)
        manager_emp.department = bd_department
        manager_emp.designation = "Business Development Manager"
        manager_emp.status = "active"
        manager_emp.date_of_joining = date(2022, 4, 1)
        manager_emp.date_of_birth = date(1990, 7, 12)
        manager_emp.show_on_tv = True
        manager_emp.save()

        for emp, _ in employees:
            emp.manager = manager_emp
            emp.save(update_fields=["manager"])
            profile = emp.user.profile
            profile.team = manager_emp.user.profile
            profile.save(update_fields=["team"])

        team_members = {}
        for username, first, last, email, designation, role_name in DEMO_TEAM_MEMBERS:
            user = self.upsert_user(username, first, last, email, role_name)
            emp = self.employee(user, bd_department, manager=manager_emp, dob=date(1992, 3, 14))
            emp.designation = designation
            emp.date_of_joining = date(2023, 6, 1)
            emp.save()
            team_members[role_name] = user

        BDEConfig.objects.update_or_create(
            pk=1,
            defaults={
                "default_target": Decimal("200000"),
                "slabs": 10,
                "red_max": 5,
                "yellow_max": 8,
                "red_pip_months": 2,
                "yellow_pip_months": 4,
                "window_months": 4,
                "appraisal_green_months": 3,
                "appraisal_mixed_green": 2,
                "appraisal_mixed_yellow": 2,
                "neutral_yellow": 3,
                "neutral_green": 1,
            },
        )

        for emp, _ in employees:
            BDETarget.objects.update_or_create(employee=emp, defaults={"monthly_target": Decimal("200000")})

        source = self.source("Website / Demo")
        months = [date(2026, m, 1) for m in (6, 7, 8, 9, 10)]

        for emp, pattern_name in employees:
            pattern = PATTERNS[pattern_name]
            for index, (month, colour) in enumerate(zip(months, pattern), 1):
                revenue = REVENUE_BY_COLOUR[colour]
                self.add_won_revenue(emp, month, revenue, source, services[(emp.pk or 1) % len(services)], index)

            self.add_pipeline_leads([emp], source, services[(emp.pk or 1) % len(services)])

        # Recalculate from the CRM source of truth, then evaluate PIP/appraisal rules.
        today = date(2026, 10, 4)
        for emp, _ in employees:
            for month in months:
                bde.recalc_month(emp, month, user=admin_user, today=today)
            bde.process_employee(emp, today=today, user=admin_user)

        # Add an explicit PIP update to the Red-PIP demo employee.
        pip_emp = next(emp for emp, pattern in employees if pattern == "pip_red")
        pip = ImprovementPlan.objects.filter(employee=pip_emp).order_by("-id").first()
        if pip:
            ImprovementUpdate.objects.get_or_create(
                plan=pip,
                date=date(2026, 10, 2),
                defaults={
                    "note": "Demo review: improve monthly revenue consistency and pipeline conversion.",
                    "score": 45,
                    "author": manager_user,
                },
             )

        self.create_delivery_plans(employees, team_members, manager_user, admin_user, today)

        TVDisplay.objects.update_or_create(
            name="LeadPlus360 Demo Performance TV",
            defaults={"department": bd_department, "seconds_per_slide": 8, "is_active": True},
        )
        for title, subtitle, order in [
            ("Demo Team Spotlight", "LeadPlus360 Business Development Performance", 1),
            ("Keep Winning", "Performance updates rotate automatically on this TV", 2),
        ]:
            TVPoster.objects.update_or_create(
                title=title,
                defaults={"subtitle": subtitle, "seconds": 8, "sort_order": order, "is_active": True},
            )

        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS("Demo data created/updated successfully."))
        self.stdout.write(self.style.SUCCESS("Dummy password for every demo user: 1234"))
        self.stdout.write("")
        self.stdout.write("Demo logins:")
        self.stdout.write("  demo_admin   / 1234")
        self.stdout.write("  demo_manager / 1234")
        for username, *_ in DEMO_EMPLOYEES:
            self.stdout.write(f"  {username:<12} / 1234")
        for username, *_ in DEMO_TEAM_MEMBERS:
            self.stdout.write(f"  {username:<12} / 1234")
