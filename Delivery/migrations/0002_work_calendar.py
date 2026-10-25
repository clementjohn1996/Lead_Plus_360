from django.db import migrations, models
import django.db.models.deletion
from django.conf import settings
from django.utils import timezone


def seed_packages(apps, schema_editor):
    Package = apps.get_model("Delivery", "DeliveryPackage")
    Task = apps.get_model("Delivery", "PackageTaskTemplate")
    presets = {
        "Digital Marketing + Website + SEO": [
            ("video", "Video production", "🎬", 7, 1),
            ("poster", "Poster creatives", "🎨", 4, 2),
            ("meta_ads", "Meta Ads setup & campaigns", "📣", 3, 3),
            ("website", "Website design & development", "💻", 14, 4),
            ("seo", "SEO setup & monthly optimization", "🔎", 7, 5),
        ],
        "Digital Marketing": [
            ("video", "Video production", "🎬", 7, 1),
            ("poster", "Poster creatives", "🎨", 4, 2),
            ("meta_ads", "Meta Ads setup & campaigns", "📣", 3, 3),
        ],
        "Website + SEO": [
            ("website", "Website design & development", "💻", 14, 1),
            ("seo", "SEO setup & monthly optimization", "🔎", 7, 2),
        ],
    }
    for name, tasks in presets.items():
        package, _ = Package.objects.get_or_create(name=name, defaults={"description": "Preset LeadPlus-360 delivery package", "is_preset": True, "is_active": True})
        for task_type, title, icon, duration, sequence in tasks:
            Task.objects.get_or_create(package=package, title=title, defaults={"task_type": task_type, "icon": icon, "default_duration_days": duration, "sequence": sequence, "active": True})


class Migration(migrations.Migration):
    dependencies = [("Delivery", "0001_initial")]
    operations = [
        migrations.CreateModel(name="DeliveryPackage", fields=[
            ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
            ("name", models.CharField(max_length=160, unique=True)), ("description", models.TextField(blank=True)),
            ("is_preset", models.BooleanField(default=True)), ("is_active", models.BooleanField(default=True)),
            ("created_at", models.DateTimeField(auto_now_add=True)), ("updated_at", models.DateTimeField(auto_now=True)),
            ("created_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="delivery_packages_created", to=settings.AUTH_USER_MODEL)),
        ], options={"ordering": ["name"]}),
        migrations.CreateModel(name="PackageTaskTemplate", fields=[
            ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
            ("task_type", models.CharField(choices=[("video", "Video production"), ("poster", "Poster / creative"), ("meta_ads", "Meta Ads"), ("website", "Website"), ("seo", "SEO"), ("custom", "Custom")], default="custom", max_length=30)),
            ("title", models.CharField(max_length=180)), ("icon", models.CharField(default="📌", max_length=20)), ("gif_url", models.URLField(blank=True)),
            ("default_duration_days", models.PositiveSmallIntegerField(default=3)), ("sequence", models.PositiveSmallIntegerField(default=1)), ("active", models.BooleanField(default=True)),
            ("package", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="task_templates", to="Delivery.deliverypackage")),
        ], options={"ordering": ["sequence", "id"]}),
        migrations.CreateModel(name="DeliveryPlan", fields=[
            ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
            ("package_name", models.CharField(blank=True, help_text="Snapshot / custom package name", max_length=180)),
            ("start_date", models.DateField(default=timezone.localdate)), ("target_completion_date", models.DateField(blank=True, null=True)),
            ("status", models.CharField(choices=[("draft", "Draft"), ("pending_approval", "Pending BDM approval"), ("changes_requested", "Changes requested"), ("approved", "Approved"), ("in_progress", "In progress"), ("completed", "Completed"), ("cancelled", "Cancelled")], db_index=True, default="draft", max_length=25)),
            ("bdm_notes", models.TextField(blank=True)), ("submitted_at", models.DateTimeField(blank=True, null=True)), ("approved_at", models.DateTimeField(blank=True, null=True)), ("created_at", models.DateTimeField(auto_now_add=True)), ("updated_at", models.DateTimeField(auto_now=True)),
            ("approved_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="delivery_plans_approved", to=settings.AUTH_USER_MODEL)),
            ("bde", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="delivery_plans_bde", to=settings.AUTH_USER_MODEL)),
            ("bdm", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="delivery_plans_bdm", to=settings.AUTH_USER_MODEL)),
            ("lead", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name="delivery_plan", to="LeadManager.lead")),
            ("package", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="plans", to="Delivery.deliverypackage")),
        ], options={"ordering": ["start_date", "-created_at"]}),
        migrations.CreateModel(name="DeliveryCalendarTask", fields=[
            ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
            ("task_type", models.CharField(choices=[("video", "Video production"), ("poster", "Poster / creative"), ("meta_ads", "Meta Ads"), ("website", "Website"), ("seo", "SEO"), ("custom", "Custom")], default="custom", max_length=30)),
            ("title", models.CharField(max_length=180)), ("description", models.TextField(blank=True)), ("icon", models.CharField(default="📌", max_length=20)), ("gif_url", models.URLField(blank=True)),
            ("assignment_role", models.CharField(choices=[("bd", "BDE / Business Development"), ("video", "Video Team"), ("design", "Design Team"), ("marketing", "Digital Marketing"), ("web", "Web Development"), ("seo", "SEO Team"), ("other", "Other")], default="other", max_length=20)),
            ("start_date", models.DateField(blank=True, null=True)), ("shoot_date", models.DateField(blank=True, null=True)), ("draft_date", models.DateField(blank=True, help_text="Expected edited/draft version", null=True)), ("launch_date", models.DateField(blank=True, help_text="Launch / implementation date", null=True)), ("final_date", models.DateField(blank=True, null=True)), ("due_date", models.DateField(blank=True, null=True)),
            ("status", models.CharField(choices=[("planned", "Planned"), ("in_progress", "In progress"), ("review", "Review"), ("completed", "Completed"), ("blocked", "Blocked"), ("cancelled", "Cancelled")], db_index=True, default="planned", max_length=20)),
            ("progress", models.PositiveSmallIntegerField(default=0)), ("notes", models.TextField(blank=True)), ("created_at", models.DateTimeField(auto_now_add=True)), ("updated_at", models.DateTimeField(auto_now=True)),
            ("assigned_to", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="delivery_calendar_tasks", to=settings.AUTH_USER_MODEL)),
            ("plan", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="tasks", to="Delivery.deliveryplan")),
            ("template", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="calendar_tasks", to="Delivery.packagetasktemplate")),
        ], options={"ordering": ["start_date", "due_date", "id"]}),
        migrations.AddIndex(model_name="deliveryplan", index=models.Index(fields=["status", "start_date"], name="Delivery_de_status_0e5e0a_idx")),
        migrations.AddIndex(model_name="deliveryplan", index=models.Index(fields=["bde", "status"], name="Delivery_de_bde_9a3f5d_idx")),
        migrations.AddIndex(model_name="deliveryplan", index=models.Index(fields=["bdm", "status"], name="Delivery_de_bdm_6dca6e_idx")),
        migrations.AddIndex(model_name="deliverycalendartask", index=models.Index(fields=["start_date", "due_date"], name="Delivery_de_start_d8d0e1_idx")),
        migrations.AddIndex(model_name="deliverycalendartask", index=models.Index(fields=["status"], name="Delivery_de_status_72d6c9_idx")),
        migrations.RunPython(seed_packages, migrations.RunPython.noop),
    ]
