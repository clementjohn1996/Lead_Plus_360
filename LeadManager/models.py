from django.conf import settings
from django.db import models
from django.utils import timezone


# ============================================================
# ABSTRACT BASE
# ============================================================

class TimeStamped(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


# ============================================================
# LEAD SOURCE
# ============================================================

class LeadSource(TimeStamped):
    name = models.CharField(max_length=80, unique=True)
    icon = models.CharField(
        max_length=30,
        blank=True,
        help_text="CSS icon class for UI (e.g. 'bi bi-google', 'bi bi-meta')",
    )
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]
        verbose_name = "Lead Source"
        verbose_name_plural = "Lead Sources"

    def __str__(self):
        return self.name


# ============================================================
# SERVICE
# ============================================================

class Service(TimeStamped):
    """
    Agency service offering. Can be tagged on multiple leads
    via Lead.services ManyToManyField.
    """

    CATEGORIES = [
        ("web_dev", "Web & App Development"),
        ("seo", "Search Engine Optimization"),
        ("meta_ads", "Meta Ads"),
        ("google_ads", "Google Ads"),
        ("media_production", "Media Production"),
        ("social_branding", "Social Media & Branding"),
    ]

    name = models.CharField(max_length=120, unique=True)
    slug = models.SlugField(max_length=120, unique=True, null=True, blank=True)
    description = models.TextField(blank=True)
    category = models.CharField(max_length=30, choices=CATEGORIES, default="web_dev")
    default_rate = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        from django.utils.text import slugify

        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)


# ============================================================
# DEPARTMENT
# ============================================================

class Department(TimeStamped):
    """
    Production / delivery department (e.g. Development PM,
    Performance Marketing Lead, Creative Director).
    Used for routing won leads to the correct team.
    """

    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=100, unique=True, null=True, blank=True)
    description = models.TextField(blank=True)
    head = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="departments_headed",
    )
    services = models.ManyToManyField(Service, related_name="departments")

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        from django.utils.text import slugify

        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)


# ============================================================
# LEAD
# ============================================================

class Lead(TimeStamped):
    """Primary B2B lead / prospect record for an agency."""

    # -- Stage state machine --
    STAGES = [
        ("new", "New"),
        ("assigned", "Assigned"),
        ("contacted", "Contacted"),
        ("in_followup", "In Follow-up"),
        ("proposal_sent", "Proposal Sent"),
        ("negotiation", "Negotiation"),
        ("won", "Won"),
        ("lost", "Lost"),
        ("disqualified", "Disqualified"),
    ]
    TEMPERATURES = [("cold", "Cold"), ("warm", "Warm"), ("hot", "Hot")]
    PRIORITIES = [
        ("low", "Low"),
        ("medium", "Medium"),
        ("high", "High"),
        ("urgent", "Urgent"),
    ]
    BUDGET_TIERS = [
        ("small", "Under 50K"),
        ("medium", "50K – 2L"),
        ("large", "2L – 10L"),
        ("enterprise", "10L+"),
    ]
    BILLING_TYPES = [
        ("onetime", "One-time"),
        ("retainer", "Monthly Retainer"),
        ("milestone", "Milestone-based"),
    ]

    # -- Identity --
    name = models.CharField(max_length=160)
    company = models.CharField(max_length=180, blank=True)
    designation = models.CharField(max_length=120, blank=True)
    industry = models.CharField(max_length=100, blank=True)

    # -- Contact --
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=40, blank=True)
    alternate_phone = models.CharField(max_length=40, blank=True)
    website = models.URLField(blank=True)
    linkedin = models.URLField(blank=True)
    facebook = models.URLField(blank=True)
    instagram = models.URLField(blank=True)

    # -- Location --
    country = models.CharField(max_length=80, blank=True)
    state = models.CharField(max_length=100, blank=True)
    city = models.CharField(max_length=100, blank=True)

    # -- Attribution --
    source = models.ForeignKey(
        LeadSource,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="leads",
    )
    # legacy single-service FK (kept for backward compatibility;
    # use services M2M going forward — see REFACTORING_ROADMAP.md step 4)
    service = models.ForeignKey(
        Service,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="leads_fk",
    )
    services = models.ManyToManyField(
        Service,
        blank=True,
        related_name="leads_m2m",
        help_text="One or more agency services the lead is interested in.",
    )

    # -- Pipeline --
    stage = models.CharField(max_length=30, choices=STAGES, default="new", db_index=True)
    temperature = models.CharField(max_length=10, choices=TEMPERATURES, default="warm")
    priority = models.CharField(max_length=10, choices=PRIORITIES, default="medium")

    # -- Assignment (RBAC) --
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="owned_leads",
    )
    manager = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="managed_leads",
    )
    assigned_at = models.DateTimeField(null=True, blank=True)

    # -- Opportunity --
    estimated_value = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    budget_tier = models.CharField(max_length=20, choices=BUDGET_TIERS, blank=True)
    billing_type = models.CharField(max_length=20, choices=BILLING_TYPES, blank=True)
    probability = models.PositiveSmallIntegerField(default=10)
    expected_close_date = models.DateField(null=True, blank=True)

    # -- Follow-up --
    next_follow_up = models.DateTimeField(null=True, blank=True, db_index=True)
    last_contacted = models.DateTimeField(null=True, blank=True)

    # -- Metadata --
    tags = models.CharField(max_length=300, blank=True)
    notes = models.TextField(blank=True)
    lost_reason = models.CharField(max_length=255, blank=True)
    consent_to_contact = models.BooleanField(default=True)

    class Meta:
        ordering = ["-updated_at"]
        indexes = [
            models.Index(fields=["stage", "owner"]),
            models.Index(fields=["next_follow_up"]),
            models.Index(fields=["created_at"]),
        ]

    @property
    def weighted_value(self):
        return (self.estimated_value * self.probability) / 100

    # --------------------------------------------------------
    # WORKFLOW METHODS
    # --------------------------------------------------------

    def reject(self, reason=None, notes=None, user=None):
        """Case A - Direct rejection: mark as lost with a structured reason + remarks."""
        self._changed_by = user
        self._status_change_reason = notes or ""
        if reason:
            self.lost_reason = reason
        self.stage = "lost"
        self.probability = 0
        self.save(update_fields=["stage", "lost_reason", "probability"])
        if reason:
            LostReasonLog.objects.update_or_create(
                lead=self,
                reason=reason,
                defaults={"notes": notes or "", "logged_by": user},
            )

    def defer(self, follow_up_date, notes=None, user=None):
        """Case B — Interested but not immediately: set follow-up reminder."""
        self._changed_by = user
        self._status_change_reason = notes or ""
        self.stage = "in_followup"
        self.next_follow_up = follow_up_date
        self.save(update_fields=["stage", "next_follow_up"])

    def accept(self, notes=None, user=None):
        """Case C — Accepted: mark as won (signals auto-generate ServiceHandover)."""
        from django.utils import timezone
        self._changed_by = user
        self._status_change_reason = notes or ""
        self.stage = "won"
        self.probability = 100
        self.save(update_fields=["stage", "probability"])

    def __str__(self):
        return f"{self.name} — {self.company}" if self.company else self.name


# ============================================================
# LEAD STATUS HISTORY (AUDIT TRAIL)
# ============================================================

class LeadStatusHistory(models.Model):
    """Immutable audit trail of every stage transition on a Lead."""

    lead = models.ForeignKey(Lead, on_delete=models.CASCADE, related_name="status_history")
    from_stage = models.CharField(max_length=30, choices=Lead.STAGES, blank=True)
    to_stage = models.CharField(max_length=30, choices=Lead.STAGES)
    changed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    changed_at = models.DateTimeField(auto_now_add=True)
    reason = models.TextField(blank=True, help_text="Reason for the status change")

    class Meta:
        ordering = ["-changed_at"]

    def __str__(self):
        return f"{self.lead} → {self.get_to_stage_display()}"


# ============================================================
# ACTIVITY (COMMUNICATION LOG)
# ============================================================

class Activity(TimeStamped):
    """Every outbound touchpoint: Call, WhatsApp, Email, Meeting, Note."""

    TYPES = [
        ("call", "Call"),
        ("email", "Email"),
        ("whatsapp", "WhatsApp"),
        ("meeting", "Meeting"),
        ("note", "Note"),
        ("status", "Status Update"),
    ]
    OUTCOMES = [
        ("connected", "Connected"),
        ("no_answer", "No Answer"),
        ("busy", "Busy"),
        ("rejected", "Rejected"),
        ("callback", "Callback Requested"),
        ("interested", "Interested"),
        ("not_interested", "Not Interested"),
    ]

    lead = models.ForeignKey(Lead, on_delete=models.CASCADE, related_name="activities")
    activity_type = models.CharField(max_length=20, choices=TYPES, default="note")
    outcome = models.CharField(max_length=20, choices=OUTCOMES, blank=True)
    subject = models.CharField(max_length=180)
    body = models.TextField(blank=True)
    due_at = models.DateTimeField(null=True, blank=True)
    completed = models.BooleanField(default=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.lead} – {self.subject}"


# ============================================================
# FOLLOW-UP SCHEDULE
# ============================================================

class FollowUpSchedule(TimeStamped):
    """
    Scheduled callbacks, reminders, and snooze management.
    Powers the Follow-Up Management Hub.
    """

    STATUSES = [
        ("pending", "Pending"),
        ("completed", "Completed"),
        ("snoozed", "Snoozed"),
        ("missed", "Missed"),
    ]

    lead = models.ForeignKey(
        Lead, on_delete=models.CASCADE, related_name="follow_ups"
    )
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    due_at = models.DateTimeField(db_index=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUSES, default="pending", db_index=True)
    snooze_until = models.DateTimeField(null=True, blank=True)
    notification_sent = models.BooleanField(default=False)
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="assigned_followups",
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_followups",
    )

    class Meta:
        ordering = ["due_at"]
        indexes = [models.Index(fields=["due_at", "status"])]

    def __str__(self):
        return f"{self.title} – due {self.due_at}"


# ============================================================
# TASK (backward compatible)
# ============================================================

class Task(TimeStamped):
    """General-purpose tasks (kept for backward compatibility)."""

    STATUSES = [("open", "Open"), ("in_progress", "In Progress"), ("done", "Done")]

    lead = models.ForeignKey(
        Lead, on_delete=models.CASCADE, related_name="tasks", null=True, blank=True
    )
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    due_at = models.DateTimeField()
    status = models.CharField(max_length=20, choices=STATUSES, default="open")
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="lead_tasks",
    )

    class Meta:
        ordering = ["status", "due_at"]

    def __str__(self):
        return self.title


# ============================================================
# LOST REASON LOG
# ============================================================

class LostReasonLog(models.Model):
    """Structured analysis record for lost or disqualified leads."""

    REASONS = [
        ("budget", "Budget Mismatch"),
        ("existing", "Already has an agency"),
        ("in_house", "In-house team"),
        ("trust", "Lack of trust"),
        ("timing", "Bad timing"),
        ("out_of_scope", "Out of scope"),
        ("competitor", "Went to competitor"),
        ("other", "Other"),
    ]

    lead = models.ForeignKey(
        Lead, on_delete=models.CASCADE, related_name="lost_reasons"
    )
    reason = models.CharField(max_length=30, choices=REASONS)
    notes = models.TextField(blank=True)
    logged_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    logged_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-logged_at"]

    def __str__(self):
        return f"{self.lead} – {self.reason}"


# ============================================================
# SERVICE HANDOVER
# ============================================================

class ServiceHandover(models.Model):
    """
    Scoping sheet created automatically when a lead is marked Won.
    Routes the lead to the correct department for production.
    """

    lead = models.ForeignKey(
        Lead, on_delete=models.CASCADE, related_name="handovers"
    )
    service = models.ForeignKey(
        Service, on_delete=models.PROTECT, related_name="handovers"
    )
    department = models.ForeignKey(
        Department, on_delete=models.PROTECT, related_name="handovers"
    )
    target_deliverable = models.CharField(max_length=200)
    target_delivery_date = models.DateField()
    approved_quote = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    billing_type = models.CharField(
        max_length=20, choices=Lead.BILLING_TYPES, default="onetime"
    )
    scope_notes = models.TextField(blank=True)
    handover_notes = models.TextField(blank=True)
    accepted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="accepted_handovers",
    )
    accepted_at = models.DateTimeField(null=True, blank=True)
    status = models.CharField(
        max_length=20,
        choices=[
            ("pending", "Pending Review"),
            ("accepted", "Accepted by Department"),
            ("rejected", "Rejected"),
        ],
        default="pending",
    )

    class Meta:
        ordering = ["-id"]
        unique_together = ("lead", "service", "department")

    def __str__(self):
        return f"Handover for {self.lead} → {self.department}"


# ============================================================
# DEAL (backward compatible)
# ============================================================

class Deal(TimeStamped):
    lead = models.OneToOneField(Lead, on_delete=models.CASCADE, related_name="deal")
    value = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    service = models.ForeignKey(
        Service, on_delete=models.SET_NULL, null=True, blank=True
    )
    expected_close = models.DateField(null=True, blank=True)
    status = models.CharField(
        max_length=20,
        choices=[("open", "Open"), ("won", "Won"), ("lost", "Lost")],
        default="open",
    )
    proposal_url = models.URLField(blank=True)
    notes = models.TextField(blank=True)
    contract_start = models.DateField(null=True, blank=True)
    renewal_date = models.DateField(null=True, blank=True, help_text="Auto-create a Renewal reminder N days before this date.")
    renewal_reminder_days = models.PositiveSmallIntegerField(default=7)

    def __str__(self):
        return f"Deal #{self.pk} — {self.lead}"


# ============================================================
# LEAD NOTE
# ============================================================

class LeadNote(TimeStamped):
    lead = models.ForeignKey(Lead, on_delete=models.CASCADE, related_name="lead_notes")
    body = models.TextField()
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )


# ============================================================
# MEETING
# ============================================================

class Meeting(TimeStamped):
    """
    Scheduled client meeting (call, video, or in-person).
    """

    MEETING_TYPES = [
        ("call", "Phone Call"),
        ("video", "Video Call"),
        ("in_person", "In-person"),
    ]
    STATUSES = [
        ("scheduled", "Scheduled"),
        ("completed", "Completed"),
        ("cancelled", "Cancelled"),
        ("rescheduled", "Rescheduled"),
    ]

    lead = models.ForeignKey(
        Lead, on_delete=models.CASCADE, related_name="meetings"
    )
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    meeting_type = models.CharField(max_length=20, choices=MEETING_TYPES, default="video")
    scheduled_at = models.DateTimeField(db_index=True)
    duration_minutes = models.PositiveSmallIntegerField(default=30)
    location = models.CharField(max_length=200, blank=True, help_text="Physical address or video link")
    status = models.CharField(max_length=20, choices=STATUSES, default="scheduled", db_index=True)
    participants = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        related_name="meetings",
        blank=True,
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="created_meetings",
    )

    class Meta:
        ordering = ["-scheduled_at"]
        indexes = [models.Index(fields=["scheduled_at", "status"])]

    def __str__(self):
        return f"{self.title} – {self.scheduled_at}"


# ============================================================
# REMINDER (meetings, renewals, contract follow-ups)
# ============================================================

class Reminder(TimeStamped):
    """
    General-purpose reminder for meetings, contract renewals,
    or any follow-up action.
    """

    TYPES = [
        ("meeting", "Meeting"),
        ("renewal", "Contract Renewal"),
        ("followup", "Lead Follow-up"),
        ("contract", "Contract Milestone"),
        ("other", "Other"),
    ]
    STATUSES = [
        ("pending", "Pending"),
        ("sent", "Notification Sent"),
        ("completed", "Completed"),
        ("snoozed", "Snoozed"),
        ("missed", "Missed"),
    ]

    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    reminder_type = models.CharField(max_length=20, choices=TYPES, default="other", db_index=True)
    due_at = models.DateTimeField(db_index=True)
    snooze_until = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUSES, default="pending", db_index=True)
    notification_sent = models.BooleanField(default=False)

    # Optional links to related objects
    related_lead = models.ForeignKey(
        Lead, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="reminders",
    )
    related_meeting = models.ForeignKey(
        Meeting, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="reminders",
    )

    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL, null=True, blank=True,
        related_name="assigned_reminders",
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL, null=True, blank=True,
        related_name="created_reminders",
    )

    class Meta:
        ordering = ["due_at"]
        indexes = [
            models.Index(fields=["due_at", "status"]),
            models.Index(fields=["reminder_type", "status"]),
        ]

    def __str__(self):
        return f"{self.title} – {self.due_at}"


# ============================================================
# PROPOSAL / QUOTATION
# ============================================================

class Proposal(TimeStamped):
    """
    Lightweight quotation / estimate builder.
    """

    BILLING_TYPES = Lead.BILLING_TYPES
    STATUSES = [
        ("draft", "Draft"),
        ("sent", "Sent to Client"),
        ("accepted", "Accepted"),
        ("rejected", "Rejected"),
        ("expired", "Expired"),
    ]

    lead = models.ForeignKey(
        Lead, on_delete=models.CASCADE, related_name="proposals"
    )
    title = models.CharField(max_length=200)
    services = models.ManyToManyField(Service, blank=True, related_name="proposals")
    billing_type = models.CharField(max_length=20, choices=BILLING_TYPES, default="retainer")
    subtotal = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    tax_rate = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    total_value = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    status = models.CharField(max_length=20, choices=STATUSES, default="draft")
    valid_until = models.DateField(null=True, blank=True)
    terms = models.TextField(blank=True, help_text="Payment terms and conditions")
    scope = models.TextField(blank=True, help_text="Detailed scope of work")
    file = models.FileField(upload_to="proposals/", blank=True, null=True)

    class Meta:
        ordering = ["-created_at"]

    @property
    def total_with_tax(self):
        return self.total_value * (1 + self.tax_rate / 100)

    def __str__(self):
        return f"{self.title} for {self.lead}"
