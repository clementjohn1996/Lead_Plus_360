import Outreach.models
import django.db.models.deletion
import django.utils.timezone
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("LeadManager", "0007_seed_core_departments"),
    ]

    operations = [
        migrations.CreateModel(
            name="OutreachSettings",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("confirmed_signals", models.JSONField(blank=True, default=list)),
                ("daily_cap", models.PositiveSmallIntegerField(default=25, help_text="Maximum emails sent per day.")),
                ("sending_paused", models.BooleanField(default=False, help_text="Kill switch: stops all sending immediately.")),
                ("sender_name", models.CharField(blank=True, help_text="Name used to sign emails.", max_length=120)),
                ("signature", models.TextField(blank=True, help_text="Optional lines under your name (title, company).")),
                ("company_address", models.TextField(blank=True, help_text="Postal address shown in every email footer (required by anti-spam law). Falls back to the address in Company branding.")),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={"verbose_name": "Outreach settings", "verbose_name_plural": "Outreach settings"},
        ),
        migrations.CreateModel(
            name="Prospect",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("company", models.CharField(max_length=200)),
                ("contact_name", models.CharField(blank=True, max_length=160)),
                ("contact_title", models.CharField(blank=True, max_length=120)),
                ("email", models.EmailField(blank=True, db_index=True, max_length=254)),
                ("email_status", models.CharField(choices=[("unknown", "Unknown"), ("verified", "Verified"), ("risky", "Risky"), ("guess", "Guess"), ("invalid", "Invalid")], default="unknown", max_length=10)),
                ("phone", models.CharField(blank=True, max_length=40)),
                ("website", models.CharField(blank=True, max_length=300)),
                ("domain", models.CharField(blank=True, db_index=True, max_length=200)),
                ("city", models.CharField(blank=True, max_length=100)),
                ("country", models.CharField(blank=True, max_length=80)),
                ("industry", models.CharField(blank=True, max_length=100)),
                ("source", models.CharField(default="manual", max_length=40)),
                ("status", models.CharField(choices=[("new", "New"), ("profiled", "Scanned"), ("qualified", "Qualified"), ("queued", "In a campaign"), ("contacted", "Contacted"), ("replied", "Replied"), ("meeting", "Meeting"), ("converted", "Converted to lead"), ("disqualified", "Disqualified"), ("unsubscribed", "Unsubscribed")], db_index=True, default="new", max_length=14)),
                ("score", models.PositiveSmallIntegerField(blank=True, null=True)),
                ("score_reason", models.TextField(blank=True)),
                ("signal_keys", models.TextField(blank=True, default="", help_text="Comma-wrapped signal keys, e.g. ,NO_HTTPS,BLOG_STALE,")),
                ("signal_data", models.JSONField(blank=True, default=dict)),
                ("unsubscribe_token", models.CharField(default=Outreach.models.new_token, editable=False, max_length=64, unique=True)),
                ("unsubscribed", models.BooleanField(default=False)),
                ("notes", models.TextField(blank=True)),
                ("last_scanned", models.DateTimeField(blank=True, null=True)),
                ("last_contacted", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("converted_lead", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="prospects", to="LeadManager.lead")),
                ("owner", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="prospects", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ["-score", "-created_at"]},
        ),
        migrations.CreateModel(
            name="Campaign",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=160)),
                ("offer", models.CharField(help_text="One plain sentence on what you do for companies like this (no pricing, no pitch).", max_length=240)),
                ("call_to_action", models.CharField(default="Worth a quick chat this week?", max_length=140)),
                ("framework", models.CharField(choices=[("pas", "Problem - Agitate - Solve"), ("aida", "Attention - Interest - Desire - Action"), ("bab", "Before - After - Bridge")], default="pas", max_length=6)),
                ("status", models.CharField(choices=[("draft", "Draft"), ("active", "Active"), ("paused", "Paused")], default="draft", max_length=8)),
                ("filters", models.JSONField(blank=True, default=dict)),
                ("followup_days_2", models.PositiveSmallIntegerField(default=3)),
                ("followup_days_3", models.PositiveSmallIntegerField(default=7)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("created_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="+", to=settings.AUTH_USER_MODEL)),
                ("service", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="campaigns", to="LeadManager.service")),
            ],
            options={"ordering": ["-created_at"]},
        ),
        migrations.CreateModel(
            name="OutboxMessage",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("step", models.PositiveSmallIntegerField(default=1)),
                ("subject", models.CharField(max_length=200)),
                ("body", models.TextField()),
                ("status", models.CharField(choices=[("draft", "Waiting for approval"), ("approved", "Approved"), ("rejected", "Rejected"), ("sent", "Sent"), ("failed", "Failed"), ("cancelled", "Cancelled")], db_index=True, default="draft", max_length=10)),
                ("approved_at", models.DateTimeField(blank=True, null=True)),
                ("sent_at", models.DateTimeField(blank=True, null=True)),
                ("error", models.CharField(blank=True, max_length=300)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("approved_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="+", to=settings.AUTH_USER_MODEL)),
                ("campaign", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="messages", to="Outreach.campaign")),
                ("prospect", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="messages", to="Outreach.prospect")),
            ],
            options={"ordering": ["created_at", "step"]},
        ),
        migrations.AddConstraint(
            model_name="outboxmessage",
            constraint=models.UniqueConstraint(fields=("prospect", "campaign", "step"), name="one_message_per_step"),
        ),
        migrations.CreateModel(
            name="ProspectEvent",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("kind", models.CharField(choices=[("note", "Note"), ("scan", "Website scan"), ("sent", "Email sent"), ("reply", "Reply"), ("status", "Status change"), ("import", "Imported")], default="note", max_length=8)),
                ("intent", models.CharField(blank=True, max_length=20)),
                ("body", models.TextField(blank=True)),
                ("created_at", models.DateTimeField(default=django.utils.timezone.now)),
                ("created_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="+", to=settings.AUTH_USER_MODEL)),
                ("prospect", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="events", to="Outreach.prospect")),
            ],
            options={"ordering": ["-created_at", "-id"]},
        ),
    ]
