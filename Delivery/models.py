from django.conf import settings
from django.db import models
from django.utils import timezone

class WorkItem(models.Model):
    STATUS = [
        ("awaiting_bdm", "Awaiting BDM"),
        ("awaiting_pm", "Awaiting Project Manager"),
        ("assigned", "Assigned to Team"),
        ("in_progress", "In Progress"),
        ("review", "Under Review"),
        ("completed", "Completed"),
        ("blocked", "Blocked"),
        ("cancelled", "Cancelled"),
    ]
    PRIORITY = [("low","Low"),("medium","Medium"),("high","High"),("urgent","Urgent")]

    lead = models.ForeignKey("LeadManager.Lead", on_delete=models.CASCADE, related_name="delivery_work")
    handover = models.ForeignKey("LeadManager.ServiceHandover", on_delete=models.SET_NULL, null=True, blank=True, related_name="delivery_work")
    title = models.CharField(max_length=220)
    description = models.TextField(blank=True)
    service = models.ForeignKey("LeadManager.Service", on_delete=models.PROTECT, null=True, blank=True, related_name="delivery_work")
    department = models.ForeignKey("LeadManager.Department", on_delete=models.PROTECT, null=True, blank=True, related_name="delivery_work")
    bde = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="delivery_bde_work")
    bdm = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="delivery_bdm_work")
    project_manager = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="delivery_pm_work")
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="delivery_created_work")
    priority = models.CharField(max_length=10, choices=PRIORITY, default="medium")
    status = models.CharField(max_length=20, choices=STATUS, default="awaiting_bdm", db_index=True)
    progress = models.PositiveSmallIntegerField(default=0)
    start_date = models.DateField(null=True, blank=True)
    due_date = models.DateField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    bdm_accepted_at = models.DateTimeField(null=True, blank=True)
    pm_accepted_at = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["status", "due_date"]),
            models.Index(fields=["bdm", "status"]),
            models.Index(fields=["project_manager", "status"]),
            models.Index(fields=["department", "status"]),
        ]

    def __str__(self):
        return f"#{self.pk} {self.title}"

    @property
    def is_overdue(self):
        return bool(self.due_date and self.due_date < timezone.localdate() and self.status not in ("completed","cancelled"))

    @property
    def current_owner_label(self):
        return dict(self.STATUS).get(self.status, self.status)


class WorkAssignment(models.Model):
    ROLE = [
        ("project_manager", "Project Manager"),
        ("developer", "Developer"),
        ("digital_marketing", "Digital Marketing"),
        ("graphic_designer", "Graphic Designer"),
        ("videographer", "Videographer"),
        ("video_editor", "Video Editor"),
        ("other", "Other"),
    ]
    STATUS = [("assigned","Assigned"),("accepted","Accepted"),("in_progress","In Progress"),("review","Review"),("completed","Completed"),("rejected","Rejected")]

    work = models.ForeignKey(WorkItem, on_delete=models.CASCADE, related_name="assignments")
    employee = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="delivery_assignments")
    assigned_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="delivery_assignments_created")
    role = models.CharField(max_length=40, choices=ROLE, default="other")
    title = models.CharField(max_length=220)
    instructions = models.TextField(blank=True)
    due_date = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS, default="assigned", db_index=True)
    progress = models.PositiveSmallIntegerField(default=0)
    accepted_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    reviewer_notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["status", "due_date", "-created_at"]

    def __str__(self):
        return f"{self.title} → {self.employee}"


class WorkEvent(models.Model):
    work = models.ForeignKey(WorkItem, on_delete=models.CASCADE, related_name="events")
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    event_type = models.CharField(max_length=40)
    from_status = models.CharField(max_length=30, blank=True)
    to_status = models.CharField(max_length=30, blank=True)
    message = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.work} · {self.event_type}"

# Calendar planning models
from .calendar_models import DeliveryPackage, PackageTaskTemplate, DeliveryPlan, DeliveryCalendarTask
