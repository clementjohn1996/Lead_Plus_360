import secrets

from django.db import models


def new_token():
    return secrets.token_urlsafe(24)


class KPI(models.Model):
    AUTO_KEYS = [
        ("leads_created", "Leads created"),
        ("leads_won", "Leads won"),
        ("revenue_won", "Revenue won"),
        ("activities_logged", "CRM activities logged"),
        ("tasks_completed", "Tasks completed"),
        ("tasks_on_time_pct", "Tasks completed on time (%)"),
        ("followups_completed", "Follow-ups completed"),
        ("handovers_accepted", "Project handovers accepted"),
        ("work_assigned", "Delivery assignments received"),
        ("work_completed", "Delivery assignments completed"),
        ("work_on_time_pct", "Delivery work completed on time (%)"),
        ("work_completion_rate", "Delivery assignment completion rate (%)"),
        ("attendance_rate", "Attendance rate (%)"),
        ("punctuality_pct", "Punctuality (%)"),
    ]

    name = models.CharField(max_length=120)
    description = models.CharField(max_length=255, blank=True)
    department = models.ForeignKey(
        "LeadManager.Department", on_delete=models.CASCADE, null=True, blank=True, related_name="kpis",
        help_text="Leave empty to apply to every department.",
    )
    auto_key = models.CharField(
        max_length=30, blank=True, choices=[("", "Manual entry")] + AUTO_KEYS,
        help_text="Computed automatically from system data when set.",
    )
    unit = models.CharField(max_length=20, blank=True, help_text="e.g. %, ₹, pts")
    weight = models.PositiveSmallIntegerField(default=1)
    higher_is_better = models.BooleanField(default=True)
    default_target = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]
        verbose_name = "KPI"

    def __str__(self):
        return self.name

    @property
    def is_auto(self):
        return bool(self.auto_key)


class KPIEntry(models.Model):
    employee = models.ForeignKey("HR.Employee", on_delete=models.CASCADE, related_name="kpi_entries")
    kpi = models.ForeignKey(KPI, on_delete=models.CASCADE, related_name="entries")
    month = models.DateField(help_text="First day of the month.")
    target = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    actual = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    note = models.CharField(max_length=255, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-month"]
        constraints = [models.UniqueConstraint(fields=["employee", "kpi", "month"], name="one_entry_per_kpi_month")]

    def __str__(self):
        return f"{self.employee} · {self.kpi} · {self.month:%b %Y}"


class TVDisplay(models.Model):
    name = models.CharField(max_length=120)
    token = models.CharField(max_length=64, unique=True, default=new_token, editable=False)
    department = models.ForeignKey(
        "LeadManager.Department", on_delete=models.SET_NULL, null=True, blank=True,
        help_text="Show only this department. Empty shows everyone.",
    )
    seconds_per_slide = models.PositiveSmallIntegerField(default=12)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]
        verbose_name = "TV display"

    def __str__(self):
        return self.name

    def regenerate_token(self):
        self.token = new_token()
        self.save(update_fields=["token"])


class TVPoster(models.Model):
    """Optional admin-authored poster inserted into public TV display playlists."""
    title = models.CharField(max_length=160)
    subtitle = models.CharField(max_length=255, blank=True)
    image = models.ImageField(upload_to="tv_posters/%Y/%m/", blank=True, null=True)
    seconds = models.PositiveSmallIntegerField(default=10)
    sort_order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["sort_order", "-created_at"]

    def __str__(self):
        return self.title


class ImprovementPlan(models.Model):
    STATUS = [
        ("draft", "Draft"), ("active", "Active"), ("under_review", "Under review"),
        ("improved", "Successfully completed"), ("extended", "Extended"),
        ("failed", "Unsuccessful"), ("closed", "Closed"), ("cancelled", "Cancelled"),
    ]
    OPEN = ("draft", "active", "under_review", "extended")

    employee = models.ForeignKey("HR.Employee", on_delete=models.CASCADE, related_name="improvement_plans")
    reason = models.TextField(help_text="Performance concerns.")
    goals = models.TextField(help_text="Improvement objectives and the support provided. One per line.")
    trigger_reason = models.CharField(max_length=255, blank=True, help_text="What triggered the plan.")
    trigger_months = models.CharField(max_length=120, blank=True, help_text="Months that triggered the plan.")
    manager = models.ForeignKey(
        "HR.Employee", on_delete=models.SET_NULL, null=True, blank=True, related_name="pips_managed"
    )
    duration_days = models.PositiveSmallIntegerField(default=60)
    target_requirements = models.TextField(blank=True, help_text="Targets the employee must reach.")
    auto_created = models.BooleanField(default=False)
    start_date = models.DateField()
    review_date = models.DateField(help_text="Date of the formal review.")
    start_score = models.PositiveSmallIntegerField(null=True, blank=True, help_text="Performance score when the plan began.")
    target_score = models.PositiveSmallIntegerField(default=60)
    status = models.CharField(max_length=15, choices=STATUS, default="active")
    outcome = models.TextField(blank=True, help_text="Final outcome notes.")
    created_by = models.ForeignKey("auth.User", on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)
    closed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["status", "review_date"]
        verbose_name = "performance improvement plan"

    def __str__(self):
        return f"PIP - {self.employee}"

    @property
    def is_open(self):
        return self.status in self.OPEN

    @property
    def is_overdue(self):
        from django.utils import timezone
        return self.is_open and self.review_date < timezone.localdate()


class ImprovementUpdate(models.Model):
    plan = models.ForeignKey(ImprovementPlan, on_delete=models.CASCADE, related_name="updates")
    date = models.DateField()
    note = models.TextField()
    score = models.PositiveSmallIntegerField(null=True, blank=True)
    author = models.ForeignKey("auth.User", on_delete=models.SET_NULL, null=True, blank=True, related_name="+")

    class Meta:
        ordering = ["-date", "-id"]


# ============================================================
# BDE TARGET TRACKING, COLOUR-CODED ACHIEVEMENT, APPRAISALS
# ============================================================

class BDEConfig(models.Model):
    """Single-row settings for BDE performance rules (pk=1). Read via BDEConfig.get()."""

    default_target = models.DecimalField(max_digits=14, decimal_places=2, default=200000)
    slabs = models.PositiveSmallIntegerField(default=10)
    red_max = models.PositiveSmallIntegerField(default=5, help_text="Slabs 1 to this number are Red.")
    yellow_max = models.PositiveSmallIntegerField(default=8, help_text="Slabs above Red up to this number are Yellow; the rest are Green.")
    red_pip_months = models.PositiveSmallIntegerField(default=2, help_text="Consecutive Red months that trigger a PIP.")
    yellow_pip_months = models.PositiveSmallIntegerField(default=4, help_text="Consecutive Yellow months that trigger a PIP.")
    window_months = models.PositiveSmallIntegerField(default=4, help_text="Completed months evaluated.")
    appraisal_green_months = models.PositiveSmallIntegerField(default=3, help_text="Green months in the window that make an employee appraisal-eligible.")
    appraisal_mixed_green = models.PositiveSmallIntegerField(default=2, help_text="Mixed rule: Green months needed ...")
    appraisal_mixed_yellow = models.PositiveSmallIntegerField(default=2, help_text="... together with this many Yellow months.")
    neutral_yellow = models.PositiveSmallIntegerField(default=3, help_text="Neutral rule: Yellow months ...")
    neutral_green = models.PositiveSmallIntegerField(default=1, help_text="... together with this many Green months.")

    class Meta:
        verbose_name = "BDE performance settings"

    def __str__(self):
        return "BDE performance settings"

    @classmethod
    def get(cls):
        return cls.objects.get_or_create(pk=1)[0]

    def clean(self):
        from django.core.exceptions import ValidationError
        if self.default_target is not None and self.default_target <= 0:
            raise ValidationError("Target must be greater than zero.")
        if not 1 <= self.red_max < self.yellow_max <= self.slabs:
            raise ValidationError("Ranges must satisfy: 1 <= red < yellow <= slabs.")
        if self.window_months < 1:
            raise ValidationError("Window must be at least one month.")


class BDETarget(models.Model):
    """Per-employee monthly target override. No row means the default target applies."""

    employee = models.OneToOneField("HR.Employee", on_delete=models.CASCADE, related_name="bde_target")
    monthly_target = models.DecimalField(max_digits=14, decimal_places=2)
    updated_at = models.DateTimeField(auto_now=True)

    def clean(self):
        from django.core.exceptions import ValidationError
        if self.monthly_target is None or self.monthly_target <= 0:
            raise ValidationError("Target must be greater than zero.")


class MonthlyPerformance(models.Model):
    COLOURS = [("red", "Red"), ("yellow", "Yellow"), ("green", "Green")]
    STATUSES = [
        ("pip", "PIP"), ("appraisal", "Appraisal"), ("neutral", "Neutral"),
        ("on_track", "On Track"), ("insufficient", "Insufficient Data"),
    ]

    employee = models.ForeignKey("HR.Employee", on_delete=models.CASCADE, related_name="monthly_performance")
    month = models.DateField(help_text="First day of the month.")
    target = models.DecimalField(max_digits=14, decimal_places=2)
    revenue = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    achievement_pct = models.DecimalField(max_digits=7, decimal_places=2, default=0)
    slab = models.PositiveSmallIntegerField(default=0, help_text="Slabs fully or partly filled (0 to configured slabs).")
    colour = models.CharField(max_length=10, choices=COLOURS, default="red")
    colour_override = models.CharField(max_length=10, choices=COLOURS, blank=True)
    category = models.CharField(max_length=30, blank=True, help_text="Performance category label.")
    status = models.CharField(max_length=15, choices=STATUSES, default="insufficient", help_text="Overall status after this month.")
    pip_status = models.CharField(max_length=15, blank=True)
    appraisal_status = models.CharField(max_length=15, blank=True)
    manager_remarks = models.TextField(blank=True)
    review_date = models.DateField(null=True, blank=True)
    is_closed = models.BooleanField(default=False, help_text="The month has ended and was finalised by the monthly run.")
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-month", "employee"]
        constraints = [
            models.UniqueConstraint(fields=["employee", "month"], name="one_performance_per_month"),
            models.CheckConstraint(condition=models.Q(revenue__gte=0), name="performance_revenue_non_negative"),
            models.CheckConstraint(condition=models.Q(target__gt=0), name="performance_target_positive"),
        ]

    def __str__(self):
        return f"{self.employee} {self.month:%b %Y}"

    @property
    def effective_colour(self):
        return self.colour_override or self.colour


class PerformanceAlert(models.Model):
    KINDS = [
        ("first_red", "First Red month"), ("pip_red", "Consecutive Red months - PIP"),
        ("third_yellow", "Third consecutive Yellow month"), ("pip_yellow", "Consecutive Yellow months - PIP"),
        ("appraisal", "Appraisal eligible"), ("target_hit", "Target achieved"),
        ("target_exceeded", "Target exceeded"), ("review_due", "Monthly review due"),
        ("pip_review_due", "PIP review due"),
    ]
    employee = models.ForeignKey("HR.Employee", on_delete=models.CASCADE, related_name="performance_alerts")
    kind = models.CharField(max_length=20, choices=KINDS)
    month = models.DateField()
    message = models.CharField(max_length=255)
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [models.UniqueConstraint(fields=["employee", "kind", "month"], name="one_alert_per_kind_month")]

    def __str__(self):
        return self.message


class Appraisal(models.Model):
    DECISIONS = [("pending", "Pending"), ("approved", "Approved"), ("deferred", "Deferred"), ("rejected", "Rejected")]

    employee = models.ForeignKey("HR.Employee", on_delete=models.CASCADE, related_name="appraisals")
    period_start = models.DateField()
    period_end = models.DateField()
    history = models.CharField(max_length=255, blank=True, help_text="Month-by-month colours.")
    avg_achievement = models.DecimalField(max_digits=7, decimal_places=2, default=0)
    green_months = models.PositiveSmallIntegerField(default=0)
    yellow_months = models.PositiveSmallIntegerField(default=0)
    red_months = models.PositiveSmallIntegerField(default=0)
    manager_comments = models.TextField(blank=True)
    strengths = models.TextField(blank=True)
    improvement_areas = models.TextField(blank=True)
    recommended_increment_pct = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    recommended_promotion = models.BooleanField(default=False)
    decision = models.CharField(max_length=10, choices=DECISIONS, default="pending")
    review_date = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-period_end", "employee"]
        constraints = [models.UniqueConstraint(fields=["employee", "period_end"], name="one_appraisal_per_period")]

    def __str__(self):
        return f"Appraisal {self.employee} to {self.period_end:%b %Y}"


class PerformanceAudit(models.Model):
    user = models.ForeignKey("auth.User", on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    employee = models.ForeignKey("HR.Employee", on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    action = models.CharField(max_length=80)
    old_value = models.CharField(max_length=255, blank=True)
    new_value = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-id"]

    def __str__(self):
        return self.action
