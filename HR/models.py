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
    is_fresher = models.BooleanField(
        "Fresher (no previous experience)", default=False,
        help_text="Experience-document steps are skipped automatically for freshers.",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["employee_code"]

    def __str__(self):
        return f"{self.employee_code} · {self.full_name}"

    @property
    def full_name(self):
        return self.user.get_full_name() or self.user.username

    @property
    def photo_url(self):
        """Profile photo (stored on the user's profile) or empty string."""
        profile = getattr(self.user, "profile", None)
        picture = getattr(profile, "profile_picture", None) if profile else None
        try:
            return picture.url if picture else ""
        except ValueError:
            return ""

    @property
    def initial(self):
        return (self.full_name[:1] or "?").upper()

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
    APPROVERS = [
        ("hr", "HR"), ("hr_manager", "HR Manager"), ("manager", "Reporting manager"), ("admin", "Super Admin"),
    ]
    VERIFIERS = [
        ("", "No separate verification"), ("hr_recruiter", "HR Recruiter"), ("hr", "HR"),
        ("manager", "Reporting manager"), ("admin", "Super Admin"),
    ]

    template = models.ForeignKey(OnboardingTemplate, on_delete=models.CASCADE, related_name="tasks")
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    category = models.CharField(max_length=20, choices=CATEGORIES, default="documents")
    responsible = models.CharField(max_length=20, choices=RESPONSIBLE, default="employee")
    due_after_days = models.PositiveSmallIntegerField(default=3)
    required = models.BooleanField(default=True)
    requires_upload = models.BooleanField(default=False)
    requires_approval = models.BooleanField(default=False, help_text="Completion must be confirmed before it counts.")
    approver = models.CharField(
        "Confirmed by", max_length=16, choices=APPROVERS, default="hr",
        help_text="Final confirmation (for example the HR Manager).",
    )
    verifier = models.CharField(
        "Verified by", max_length=16, choices=VERIFIERS, blank=True, default="",
        help_text="Optional first check before confirmation (for example the HR Recruiter).",
    )
    skippable = models.BooleanField(
        "Employee can skip", default=False, help_text="Shows a Skip button to the employee.",
    )
    skip_label = models.CharField(max_length=60, blank=True, help_text='Button text, e.g. "Skip - not applicable".')
    skip_if_fresher = models.BooleanField(
        "Skip automatically for freshers", default=False,
        help_text="Used for experience documents when the candidate has no previous job.",
    )
    auto_key = models.CharField(max_length=30, blank=True, choices=AUTO_KEYS)
    order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["order", "id"]

    def __str__(self):
        return self.title


class OnboardingTask(models.Model):
    STATUSES = [
        ("pending", "Pending"), ("submitted", "Awaiting verification"),
        ("verified", "Verified - awaiting confirmation"), ("done", "Done"), ("skipped", "Skipped"),
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
    approver = models.CharField(max_length=16, choices=OnboardingTemplateTask.APPROVERS, default="hr")
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    verifier = models.CharField(max_length=16, choices=OnboardingTemplateTask.VERIFIERS, blank=True, default="")
    verified_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    verified_at = models.DateTimeField(null=True, blank=True)
    skippable = models.BooleanField(default=False)
    skip_label = models.CharField(max_length=60, blank=True)
    skip_if_fresher = models.BooleanField(default=False)
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

    # ---- review chain: employee submits -> verifier verifies -> approver confirms ----
    @property
    def review_stage(self):
        """Which review the task is waiting for: "verify", "approve" or None."""
        if self.status == "submitted":
            return "verify" if self.verifier else "approve"
        if self.status == "verified":
            return "approve"
        return None

    def _is_own_task(self, user):
        return user.pk == self.employee.user_id and not user.is_superuser

    @staticmethod
    def _role_in(user, *names):
        from Control.permissions import role_name

        return role_name(user) in names

    def _matches(self, key, user):
        from Control.permissions import is_hr

        if key == "hr":
            return is_hr(user)
        if key == "hr_recruiter":
            return self._role_in(user, "hr_recruiter")
        if key == "hr_manager":
            return self._role_in(user, "hr", "hr_manager", "management")
        if key == "manager":
            manager = self.employee.manager
            return bool(manager and manager.user_id == user.pk)
        return False

    def can_verify(self, user):
        """Whether `user` may verify this task (first check). Nobody verifies their own work."""
        from Control.permissions import is_admin

        if self._is_own_task(user):
            return False
        if is_admin(user):
            return True
        return bool(self.verifier) and self._matches(self.verifier, user)

    def can_approve(self, user):
        """Whether `user` may confirm/reject this task. Nobody approves their own work."""
        from Control.permissions import is_admin

        if self._is_own_task(user):
            return False
        if is_admin(user):
            return True
        return self._matches(self.approver, user)

    def can_review_now(self, user):
        stage = self.review_stage
        if stage == "verify":
            return self.can_verify(user) or (not self.verifier and self.can_approve(user))
        if stage == "approve":
            return self.can_approve(user)
        return False

    def complete(self, user):
        """Finish the task, or send it into the review chain when the workflow requires it."""
        needs_review = self.requires_approval or bool(self.verifier)
        can_finish = (not self.verifier or self.can_verify(user)) and (
            not self.requires_approval or self.can_approve(user)
        )
        if needs_review and not can_finish:
            self.status = "submitted"
            self.completed_at = timezone.now()
            self.completed_by = user
            self.save(update_fields=["status", "completed_at", "completed_by"])
            return "submitted"
        self.mark_done(user)
        return "done"

    def verify(self, user):
        """Verifier signs off. Moves to confirmation when one is required, otherwise finishes."""
        self.verified_by = user
        self.verified_at = timezone.now()
        if self.requires_approval:
            self.status = "verified"
            self.save(update_fields=["status", "verified_by", "verified_at"])
            return "verified"
        self.save(update_fields=["verified_by", "verified_at"])
        self.mark_done(self.completed_by or user)
        return "done"

    def mark_done(self, user=None):
        self.status = "done"
        self.completed_at = timezone.now()
        self.completed_by = user
        self.save(update_fields=["status", "completed_at", "completed_by"])

    def mark_skipped(self, user=None):
        self.status = "skipped"
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
