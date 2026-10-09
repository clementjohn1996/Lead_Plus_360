from datetime import time

from django.conf import settings
from django.db import models
from django.utils import timezone


class Employee(models.Model):
    STATUSES = [
        ("onboarding", "Onboarding"),
        ("probation", "Probation"),
        ("active", "Active"),
        ("notice", "Serving notice"),
        ("exited", "Exited"),
    ]
    EMPLOYMENT_TYPES = [
        ("full_time", "Full-time"),
        ("part_time", "Part-time"),
        ("contract", "Contract"),
        ("intern", "Intern"),
    ]
    WORK_MODES = [
        ("office", "Office"),
        ("hybrid", "Hybrid"),
        ("remote", "Remote"),
    ]

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="employee")
    employee_code = models.CharField(max_length=20, unique=True, editable=False)
    department = models.ForeignKey(
        "LeadManager.Department", on_delete=models.SET_NULL, null=True, blank=True, related_name="employees"
    )
    designation = models.CharField(max_length=120, blank=True)
    manager = models.ForeignKey(
        "self", on_delete=models.SET_NULL, null=True, blank=True, related_name="reports"
    )
    employment_type = models.CharField(max_length=20, choices=EMPLOYMENT_TYPES, default="full_time")
    work_mode = models.CharField(max_length=10, choices=WORK_MODES, default="office")
    status = models.CharField(max_length=20, choices=STATUSES, default="onboarding", db_index=True)
    date_of_joining = models.DateField(default=timezone.localdate)
    date_of_birth = models.DateField(null=True, blank=True, help_text="Used for employee birthday recognition on TV displays.")
    date_of_exit = models.DateField(null=True, blank=True)
    personal_email = models.EmailField(blank=True)
    emergency_contact = models.CharField(max_length=160, blank=True)
    shift_start = models.TimeField(default=time(9, 30))
    shift_end = models.TimeField(default=time(18, 30))
    grace_minutes = models.PositiveSmallIntegerField(default=15)
    show_on_tv = models.BooleanField(default=True, help_text="Include on the TV performance display.")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["employee_code"]

    def __str__(self):
        return f"{self.employee_code} · {self.full_name}"

    @property
    def full_name(self):
        return self.user.get_full_name() or self.user.username

    @property
    def can_punch_remotely(self):
        return self.work_mode in ("remote", "hybrid")

    def save(self, *args, **kwargs):
        if not self.employee_code:
            self.employee_code = self.next_code()
        super().save(*args, **kwargs)

    @classmethod
    def next_code(cls):
        last = cls.objects.order_by("-id").values_list("employee_code", flat=True).first()
        number = 0
        if last and last.rsplit("-", 1)[-1].isdigit():
            number = int(last.rsplit("-", 1)[-1])
        return f"EMP-{number + 1:04d}"

    def onboarding_progress(self):
        tasks = self.onboarding_tasks.all()
        total = tasks.count()
        done = tasks.filter(status__in=["done", "skipped"]).count()
        return {"done": done, "total": total, "percent": int(done * 100 / total) if total else 100}


class OnboardingTemplate(models.Model):
    name = models.CharField(max_length=120, unique=True)
    department = models.ForeignKey(
        "LeadManager.Department", on_delete=models.CASCADE, null=True, blank=True,
        related_name="onboarding_templates",
        help_text="Leave empty for the company-wide default.",
    )
    role = models.ForeignKey(
        "Control.Role", on_delete=models.CASCADE, null=True, blank=True, related_name="onboarding_templates",
        help_text="Use this workflow for new joiners in this role. Role beats department.",
    )
    is_default = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.name


class OnboardingTemplateTask(models.Model):
    RESPONSIBLE = [("employee", "Employee"), ("hr", "HR"), ("manager", "Reporting manager"), ("it", "IT / Admin")]
    CATEGORIES = [
        ("documents", "Documents"),
        ("setup", "Accounts & equipment"),
        ("compliance", "Policies & compliance"),
        ("orientation", "Orientation & training"),
        ("attendance", "Attendance"),
    ]
    AUTO_KEYS = [("", "Manual"), ("face_enrollment", "Auto: face enrollment completed")]
    APPROVERS = [("hr", "HR"), ("manager", "Reporting manager"), ("admin", "Super Admin")]

    template = models.ForeignKey(OnboardingTemplate, on_delete=models.CASCADE, related_name="tasks")
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    category = models.CharField(max_length=20, choices=CATEGORIES, default="documents")
    responsible = models.CharField(max_length=20, choices=RESPONSIBLE, default="employee")
    due_after_days = models.PositiveSmallIntegerField(default=3)
    required = models.BooleanField(default=True)
    requires_upload = models.BooleanField(default=False)
    requires_approval = models.BooleanField(default=False, help_text="Completion must be approved before it counts.")
    approver = models.CharField(max_length=10, choices=APPROVERS, default="hr")
    auto_key = models.CharField(max_length=30, blank=True, choices=AUTO_KEYS)
    order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["order", "id"]

    def __str__(self):
        return self.title


class OnboardingTask(models.Model):
    STATUSES = [
        ("pending", "Pending"), ("submitted", "Awaiting approval"), ("done", "Done"), ("skipped", "Skipped"),
    ]

    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name="onboarding_tasks")
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    category = models.CharField(max_length=20, choices=OnboardingTemplateTask.CATEGORIES, default="documents")
    responsible = models.CharField(max_length=20, choices=OnboardingTemplateTask.RESPONSIBLE, default="employee")
    due_date = models.DateField(null=True, blank=True)
    required = models.BooleanField(default=True)
    requires_upload = models.BooleanField(default=False)
    requires_approval = models.BooleanField(default=False)
    approver = models.CharField(max_length=10, choices=OnboardingTemplateTask.APPROVERS, default="hr")
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    auto_key = models.CharField(max_length=30, blank=True)
    status = models.CharField(max_length=10, choices=STATUSES, default="pending", db_index=True)
    attachment = models.FileField(upload_to="onboarding/%Y/%m/", blank=True, null=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    completed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    order = models.PositiveSmallIntegerField(default=0)
    submission_count = models.PositiveSmallIntegerField(default=0, help_text="How many times the employee has submitted this task. Only HR can reset.")

    class Meta:
        ordering = ["order", "id"]

    def __str__(self):
        return f"{self.employee.employee_code}: {self.title}"

    @property
    def is_overdue(self):
        return bool(self.status == "pending" and self.due_date and self.due_date < timezone.localdate())

    @property
    def employee_locked(self):
        """Employee can only submit/complete a task once. HR can always reset via 'reopen'."""
        return self.submission_count >= 1

    def can_approve(self, user):
        """Whether `user` may approve/reject this task. Nobody approves their own work."""
        from Control.permissions import is_admin, is_hr

        if user.pk == self.employee.user_id and not user.is_superuser:
            return False
        if is_admin(user):
            return True
        if self.approver == "hr":
            return is_hr(user)
        if self.approver == "manager":
            manager = self.employee.manager
            return bool(manager and manager.user_id == user.pk)
        return False

    def complete(self, user):
        """Finish the task, or send it for approval when the workflow requires it."""
        if self.requires_approval and not self.can_approve(user):
            self.status = "submitted"
            self.completed_at = timezone.now()
            self.completed_by = user
            self.save(update_fields=["status", "completed_at", "completed_by"])
            return "submitted"
        self.mark_done(user)
        return "done"

    def mark_done(self, user=None):
        self.status = "done"
        self.completed_at = timezone.now()
        self.completed_by = user
        self.save(update_fields=["status", "completed_at", "completed_by"])


class EmployeeDocument(models.Model):
    TYPES = [
        ("id_proof", "ID proof"),
        ("address_proof", "Address proof"),
        ("education", "Education certificate"),
        ("experience", "Experience letter"),
        ("offer_letter", "Offer letter"),
        ("contract", "Signed contract"),
        ("other", "Other"),
    ]

    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name="documents")
    doc_type = models.CharField(max_length=20, choices=TYPES, default="other")
    title = models.CharField(max_length=160)
    file = models.FileField(upload_to="employee_docs/%Y/%m/")
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-uploaded_at"]

    def __str__(self):
        return self.title
