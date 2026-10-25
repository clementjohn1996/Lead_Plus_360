import secrets

from django.conf import settings
from django.db import models
from django.utils import timezone


def new_token():
    return secrets.token_urlsafe(24)


class OutreachSettings(models.Model):
    """Singleton: which signals are confirmed, sending limits and sender identity."""

    confirmed_signals = models.JSONField(default=list, blank=True)
    daily_cap = models.PositiveSmallIntegerField(default=25, help_text="Maximum emails sent per day.")
    sending_paused = models.BooleanField(default=False, help_text="Kill switch: stops all sending immediately.")
    sender_name = models.CharField(max_length=120, blank=True, help_text="Name used to sign emails.")
    signature = models.TextField(blank=True, help_text="Optional lines under your name (title, company).")
    company_address = models.TextField(
        blank=True, help_text="Postal address shown in every email footer (required by anti-spam law). "
                              "Falls back to the address in Company branding.",
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Outreach settings"
        verbose_name_plural = "Outreach settings"

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)

    @classmethod
    def get_solo(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj


class Prospect(models.Model):
    STATUSES = [
        ("new", "New"), ("profiled", "Scanned"), ("qualified", "Qualified"), ("queued", "In a campaign"),
        ("contacted", "Contacted"), ("replied", "Replied"), ("meeting", "Meeting"),
        ("converted", "Converted to lead"), ("disqualified", "Disqualified"), ("unsubscribed", "Unsubscribed"),
    ]
    EMAIL_STATUSES = [
        ("unknown", "Unknown"), ("verified", "Verified"), ("risky", "Risky"), ("guess", "Guess"), ("invalid", "Invalid"),
    ]

    company = models.CharField(max_length=200)
    contact_name = models.CharField(max_length=160, blank=True)
    contact_title = models.CharField(max_length=120, blank=True)
    email = models.EmailField(blank=True, db_index=True)
    email_status = models.CharField(max_length=10, choices=EMAIL_STATUSES, default="unknown")
    phone = models.CharField(max_length=40, blank=True)
    website = models.CharField(max_length=300, blank=True)
    domain = models.CharField(max_length=200, blank=True, db_index=True)
    city = models.CharField(max_length=100, blank=True)
    country = models.CharField(max_length=80, blank=True)
    industry = models.CharField(max_length=100, blank=True)
    source = models.CharField(max_length=40, default="manual")
    status = models.CharField(max_length=14, choices=STATUSES, default="new", db_index=True)
    score = models.PositiveSmallIntegerField(null=True, blank=True)
    score_reason = models.TextField(blank=True)
    signal_keys = models.TextField(blank=True, default="", help_text="Comma-wrapped signal keys, e.g. ,NO_HTTPS,BLOG_STALE,")
    signal_data = models.JSONField(default=dict, blank=True)
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="prospects"
    )
    converted_lead = models.ForeignKey(
        "LeadManager.Lead", on_delete=models.SET_NULL, null=True, blank=True, related_name="prospects"
    )
    unsubscribe_token = models.CharField(max_length=64, unique=True, default=new_token, editable=False)
    unsubscribed = models.BooleanField(default=False)
    notes = models.TextField(blank=True)
    last_scanned = models.DateTimeField(null=True, blank=True)
    last_contacted = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-score", "-created_at"]

    def __str__(self):
        return self.company

    @property
    def signals(self):
        return [k for k in self.signal_keys.split(",") if k]

    def set_signals(self, keys):
        keys = sorted(set(keys))
        self.signal_keys = ("," + ",".join(keys) + ",") if keys else ""

    @property
    def first_name(self):
        return self.contact_name.split()[0] if self.contact_name.strip() else ""

    @property
    def can_email(self):
        return bool(self.email) and not self.unsubscribed and self.email_status != "invalid" and \
            self.status not in ("unsubscribed", "disqualified", "converted")

    @property
    def whatsapp_url(self):
        digits = "".join(ch for ch in self.phone if ch.isdigit())
        return f"https://wa.me/{digits}" if len(digits) >= 8 else ""


class Campaign(models.Model):
    STATUSES = [("draft", "Draft"), ("active", "Active"), ("paused", "Paused")]
    FRAMEWORKS = [("pas", "Problem - Agitate - Solve"), ("aida", "Attention - Interest - Desire - Action"),
                  ("bab", "Before - After - Bridge")]

    name = models.CharField(max_length=160)
    service = models.ForeignKey(
        "LeadManager.Service", on_delete=models.SET_NULL, null=True, blank=True, related_name="campaigns"
    )
    offer = models.CharField(
        max_length=240, help_text="One plain sentence on what you do for companies like this (no pricing, no pitch).",
    )
    call_to_action = models.CharField(max_length=140, default="Worth a quick chat this week?")
    framework = models.CharField(max_length=6, choices=FRAMEWORKS, default="pas")
    status = models.CharField(max_length=8, choices=STATUSES, default="draft")
    filters = models.JSONField(default=dict, blank=True)
    followup_days_2 = models.PositiveSmallIntegerField(default=3)
    followup_days_3 = models.PositiveSmallIntegerField(default=7)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.name


class PitchTemplate(models.Model):
    """Reusable client pitch owned by its author, with optional business-type targeting."""

    name = models.CharField(max_length=120)
    business_type = models.CharField(max_length=100, blank=True, help_text="Leave blank to use for any business type.")
    subject = models.CharField(max_length=200)
    body = models.TextField(help_text="Available placeholders: {{first_name}}, {{contact_name}}, {{company}}, {{industry}}, {{sender_name}}, {{company_address}}.")
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="pitch_templates")
    is_active = models.BooleanField(default=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class OutboxMessage(models.Model):
    STATUSES = [
        ("draft", "Waiting for approval"), ("approved", "Approved"), ("rejected", "Rejected"),
        ("sent", "Sent"), ("failed", "Failed"), ("cancelled", "Cancelled"),
    ]

    prospect = models.ForeignKey(Prospect, on_delete=models.CASCADE, related_name="messages")
    campaign = models.ForeignKey(Campaign, on_delete=models.CASCADE, related_name="messages")
    step = models.PositiveSmallIntegerField(default=1)
    subject = models.CharField(max_length=200)
    body = models.TextField()
    status = models.CharField(max_length=10, choices=STATUSES, default="draft", db_index=True)
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    approved_at = models.DateTimeField(null=True, blank=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    error = models.CharField(max_length=300, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at", "step"]
        constraints = [
            models.UniqueConstraint(fields=["prospect", "campaign", "step"], name="one_message_per_step")
        ]

    def __str__(self):
        return f"{self.prospect} · step {self.step}"


class ProspectEvent(models.Model):
    KINDS = [("note", "Note"), ("scan", "Website scan"), ("sent", "Email sent"), ("reply", "Reply"),
             ("status", "Status change"), ("import", "Imported")]

    prospect = models.ForeignKey(Prospect, on_delete=models.CASCADE, related_name="events")
    kind = models.CharField(max_length=8, choices=KINDS, default="note")
    intent = models.CharField(max_length=20, blank=True)
    body = models.TextField(blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["-created_at", "-id"]
