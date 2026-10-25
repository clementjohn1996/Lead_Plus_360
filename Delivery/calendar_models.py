from datetime import timedelta

from django.conf import settings
from django.db import models
from django.utils import timezone


class DeliveryPackage(models.Model):
    """Reusable delivery package blueprint; admins can create custom packages too."""
    name = models.CharField(max_length=160, unique=True)
    description = models.TextField(blank=True)
    is_preset = models.BooleanField(default=True)
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="delivery_packages_created")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class PackageTaskTemplate(models.Model):
    TASK_TYPES = [
        ("video", "Video production"),
        ("poster", "Poster / creative"),
        ("meta_ads", "Meta Ads"),
        ("website", "Website"),
        ("seo", "SEO"),
        ("custom", "Custom"),
    ]
    package = models.ForeignKey(DeliveryPackage, on_delete=models.CASCADE, related_name="task_templates")
    task_type = models.CharField(max_length=30, choices=TASK_TYPES, default="custom")
    title = models.CharField(max_length=180)
    icon = models.CharField(max_length=20, default="📌")
    gif_url = models.URLField(blank=True, help_text="Optional animated GIF URL; icon is used when empty.")
    default_duration_days = models.PositiveSmallIntegerField(default=3)
    sequence = models.PositiveSmallIntegerField(default=1)
    active = models.BooleanField(default=True)

    class Meta:
        ordering = ["sequence", "id"]

    def __str__(self):
        return f"{self.package} · {self.title}"


class DeliveryPlan(models.Model):
    STATUS = [
        ("draft", "Draft"),
        ("pending_approval", "Pending BDM approval"),
        ("changes_requested", "Changes requested"),
        ("approved", "Approved"),
        ("in_progress", "In progress"),
        ("completed", "Completed"),
        ("cancelled", "Cancelled"),
    ]
    lead = models.OneToOneField("LeadManager.Lead", on_delete=models.CASCADE, related_name="delivery_plan")
    package = models.ForeignKey(DeliveryPackage, on_delete=models.PROTECT, null=True, blank=True, related_name="plans")
    package_name = models.CharField(max_length=180, blank=True, help_text="Snapshot / custom package name")
    bde = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="delivery_plans_bde")
    bdm = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="delivery_plans_bdm")
    start_date = models.DateField(default=timezone.localdate)
    target_completion_date = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=25, choices=STATUS, default="draft", db_index=True)
    bdm_notes = models.TextField(blank=True)
    submitted_at = models.DateTimeField(null=True, blank=True)
    approved_at = models.DateTimeField(null=True, blank=True)
    approved_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="delivery_plans_approved")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["start_date", "-created_at"]
        indexes = [models.Index(fields=["status", "start_date"]), models.Index(fields=["bde", "status"]), models.Index(fields=["bdm", "status"])]

    def __str__(self):
        return f"{self.lead} · {self.package_name or self.package}"

    @property
    def client_name(self):
        return self.lead.company or self.lead.name

    @property
    def progress(self):
        tasks = list(self.tasks.all())
        if not tasks:
            return 0
        return round(sum(t.progress for t in tasks) / len(tasks))


class DeliveryCalendarTask(models.Model):
    STATUS = [
        ("planned", "Planned"),
        ("in_progress", "In progress"),
        ("review", "Review"),
        ("completed", "Completed"),
        ("blocked", "Blocked"),
        ("cancelled", "Cancelled"),
    ]
    TASK_TYPES = PackageTaskTemplate.TASK_TYPES
    ASSIGNMENT_ROLES = [
        ("bd", "BDE / Business Development"),
        ("video", "Video Team"),
        ("design", "Design Team"),
        ("marketing", "Digital Marketing"),
        ("web", "Web Development"),
        ("seo", "SEO Team"),
        ("other", "Other"),
    ]
    plan = models.ForeignKey(DeliveryPlan, on_delete=models.CASCADE, related_name="tasks")
    template = models.ForeignKey(PackageTaskTemplate, on_delete=models.SET_NULL, null=True, blank=True, related_name="calendar_tasks")
    task_type = models.CharField(max_length=30, choices=TASK_TYPES, default="custom")
    title = models.CharField(max_length=180)
    description = models.TextField(blank=True)
    icon = models.CharField(max_length=20, default="📌")
    gif_url = models.URLField(blank=True)
    assignment_role = models.CharField(max_length=20, choices=ASSIGNMENT_ROLES, default="other")
    assigned_to = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="delivery_calendar_tasks")
    start_date = models.DateField(null=True, blank=True)
    shoot_date = models.DateField(null=True, blank=True)
    draft_date = models.DateField(null=True, blank=True, help_text="Expected edited/draft version")
    launch_date = models.DateField(null=True, blank=True, help_text="Launch / implementation date")
    final_date = models.DateField(null=True, blank=True)
    due_date = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS, default="planned", db_index=True)
    progress = models.PositiveSmallIntegerField(default=0)
    notes = models.TextField(blank=True)
    reminder_enabled = models.BooleanField(default=False, help_text="Send a notification before this task starts.")
    reminder_days_before = models.PositiveSmallIntegerField(default=1, help_text="Minimum 1 day before start date.")
    reminder_sent = models.BooleanField(default=False, help_text="Internal: whether the reminder was already sent.")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["start_date", "due_date", "id"]
        indexes = [models.Index(fields=["start_date", "due_date"]), models.Index(fields=["status"]), models.Index(fields=["reminder_enabled", "reminder_sent"])]

    def __str__(self):
        return f"{self.icon} {self.title} · {self.plan.client_name}"

    @property
    def display_date(self):
        return self.start_date or self.due_date or self.final_date

    @property
    def reminder_date(self):
        if self.reminder_enabled and self.start_date:
            return self.start_date - timedelta(days=max(self.reminder_days_before, 1))
        return None

    @property
    def is_reminder_due(self):
        from django.utils import timezone
        rd = self.reminder_date
        today = timezone.localdate()
        return bool(rd and rd <= today and not self.reminder_sent and self.start_date > today)
