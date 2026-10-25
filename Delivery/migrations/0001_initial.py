from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion

class Migration(migrations.Migration):
    initial = True
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("LeadManager", "0006_deal_contract_start_deal_renewal_date_and_more"),
    ]
    operations = [
        migrations.CreateModel(
            name="WorkItem",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("title", models.CharField(max_length=220)),
                ("description", models.TextField(blank=True)),
                ("priority", models.CharField(choices=[("low","Low"),("medium","Medium"),("high","High"),("urgent","Urgent")], default="medium", max_length=10)),
                ("status", models.CharField(choices=[("awaiting_bdm","Awaiting BDM"),("awaiting_pm","Awaiting Project Manager"),("assigned","Assigned to Team"),("in_progress","In Progress"),("review","Under Review"),("completed","Completed"),("blocked","Blocked"),("cancelled","Cancelled")], db_index=True, default="awaiting_bdm", max_length=20)),
                ("progress", models.PositiveSmallIntegerField(default=0)),
                ("start_date", models.DateField(blank=True, null=True)),
                ("due_date", models.DateField(blank=True, null=True)),
                ("completed_at", models.DateTimeField(blank=True, null=True)),
                ("bdm_accepted_at", models.DateTimeField(blank=True, null=True)),
                ("pm_accepted_at", models.DateTimeField(blank=True, null=True)),
                ("notes", models.TextField(blank=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("bde", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="delivery_bde_work", to=settings.AUTH_USER_MODEL)),
                ("bdm", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="delivery_bdm_work", to=settings.AUTH_USER_MODEL)),
                ("created_by", models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="delivery_created_work", to=settings.AUTH_USER_MODEL)),
                ("department", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="delivery_work", to="LeadManager.department")),
                ("handover", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="delivery_work", to="LeadManager.servicehandover")),
                ("lead", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="delivery_work", to="LeadManager.lead")),
                ("project_manager", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="delivery_pm_work", to=settings.AUTH_USER_MODEL)),
                ("service", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="delivery_work", to="LeadManager.service")),
            ],
            options={"ordering":["-created_at"]},
        ),
        migrations.CreateModel(
            name="WorkAssignment",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("role", models.CharField(choices=[("project_manager","Project Manager"),("developer","Developer"),("digital_marketing","Digital Marketing"),("graphic_designer","Graphic Designer"),("videographer","Videographer"),("video_editor","Video Editor"),("other","Other")], default="other", max_length=40)),
                ("title", models.CharField(max_length=220)),
                ("instructions", models.TextField(blank=True)),
                ("due_date", models.DateField(blank=True, null=True)),
                ("status", models.CharField(choices=[("assigned","Assigned"),("accepted","Accepted"),("in_progress","In Progress"),("review","Review"),("completed","Completed"),("rejected","Rejected")], db_index=True, default="assigned", max_length=20)),
                ("progress", models.PositiveSmallIntegerField(default=0)),
                ("accepted_at", models.DateTimeField(blank=True, null=True)),
                ("completed_at", models.DateTimeField(blank=True, null=True)),
                ("reviewer_notes", models.TextField(blank=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("assigned_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="delivery_assignments_created", to=settings.AUTH_USER_MODEL)),
                ("employee", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="delivery_assignments", to=settings.AUTH_USER_MODEL)),
                ("work", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="assignments", to="Delivery.workitem")),
            ],
            options={"ordering":["status","due_date","-created_at"]},
        ),
        migrations.CreateModel(
            name="WorkEvent",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("event_type", models.CharField(max_length=40)),
                ("from_status", models.CharField(blank=True, max_length=30)),
                ("to_status", models.CharField(blank=True, max_length=30)),
                ("message", models.TextField(blank=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("actor", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL)),
                ("work", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="events", to="Delivery.workitem")),
            ],
            options={"ordering":["-created_at"]},
        ),
        migrations.AddIndex(model_name="workitem", index=models.Index(fields=["status","due_date"], name="Delivery_wo_status_9cbd8c_idx")),
        migrations.AddIndex(model_name="workitem", index=models.Index(fields=["bdm","status"], name="Delivery_wo_bdm_id_4d5f2e_idx")),
        migrations.AddIndex(model_name="workitem", index=models.Index(fields=["project_manager","status"], name="Delivery_wo_project_6d9a7c_idx")),
        migrations.AddIndex(model_name="workitem", index=models.Index(fields=["department","status"], name="Delivery_wo_depart_0a0c3b_idx")),
    ]
