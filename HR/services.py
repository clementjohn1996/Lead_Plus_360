import secrets
import string
from datetime import timedelta

from django.contrib.auth.models import User
from django.db import transaction

from Control.models import Role, UserProfile

from .models import Employee, OnboardingTask, OnboardingTemplate


def generate_password(length=12):
    alphabet = string.ascii_letters + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(length))


def pick_template(employee):
    """Most specific workflow wins: role, then department, then the company default."""
    qs = OnboardingTemplate.objects.filter(is_active=True)
    role = Role.objects.filter(users__user_id=employee.user_id).first()
    if role:
        template = qs.filter(role=role).first()
        if template:
            return template
    if employee.department_id:
        template = qs.filter(department=employee.department).first()
        if template:
            return template
    return qs.filter(is_default=True).first()


def generate_onboarding(employee):
    """Create the employee's checklist from the matching template (idempotent)."""
    if employee.onboarding_tasks.exists():
        return 0
    template = pick_template(employee)
    if not template:
        return 0
    tasks = [
        OnboardingTask(
            employee=employee,
            title=t.title,
            description=t.description,
            category=t.category,
            responsible=t.responsible,
            due_date=employee.date_of_joining + timedelta(days=t.due_after_days),
            required=t.required,
            requires_upload=t.requires_upload,
            requires_approval=t.requires_approval,
            approver=t.approver,
            auto_key=t.auto_key,
            order=t.order,
        )
        for t in template.tasks.all()
    ]
    OnboardingTask.objects.bulk_create(tasks)
    sync_auto_tasks(employee)
    return len(tasks)


def sync_auto_tasks(employee):
    """Complete tasks whose condition is already satisfied by system data."""
    from Attendance.models import FaceTemplate

    if FaceTemplate.objects.filter(employee=employee).exists():
        for task in employee.onboarding_tasks.filter(auto_key="face_enrollment", status="pending"):
            task.mark_done()


def refresh_status(employee):
    """Move an onboarding employee to active once every required task is finished."""
    if employee.status != "onboarding":
        return False
    pending = employee.onboarding_tasks.filter(required=True, status__in=["pending", "submitted"]).exists()
    if employee.onboarding_tasks.exists() and not pending:
        employee.status = "active"
        employee.save(update_fields=["status"])
        return True
    return False


@transaction.atomic
def create_employee(*, username, first_name, last_name, email, role_name="developer", password=None, **fields):
    """Create login + role + employee record + onboarding checklist. Returns (employee, password)."""
    password = password or generate_password()
    user = User.objects.create_user(
        username=username, email=email, password=password, first_name=first_name, last_name=last_name
    )
    profile, _ = UserProfile.objects.get_or_create(user=user)
    profile.role = Role.objects.filter(name=role_name).first()
    profile.save(update_fields=["role"])
    employee = Employee.objects.create(user=user, **fields)
    generate_onboarding(employee)
    return employee, password
