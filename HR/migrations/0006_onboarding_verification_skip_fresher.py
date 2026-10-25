from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion

OLD_TITLE = "Submit education & experience documents"

# (title, description, skip_label, skip_if_fresher)
EDUCATION = [
    ("Education: High school certificate", "Upload your high school (10th / SSLC) mark sheet or certificate.", "Skip - not applicable", False),
    ("Education: Higher secondary certificate", "Upload your higher secondary (12th / Plus Two) mark sheet or certificate.", "Skip - not applicable", False),
    ("Education: Graduation certificate", "Upload your degree certificate or provisional certificate.", "Skip - not applicable", False),
    ("Education: Post-graduation certificate", "Upload your post-graduation certificate, if you have one.", "Skip - not applicable", False),
]
EXPERIENCE = [
    ("Experience: Latest employer", "Upload the experience / relieving letter from your latest employer.", "I'm a fresher - skip", True),
    ("Experience: Previous employer I", "Upload the experience letter from your previous employer.", "Skip - not applicable", True),
    ("Experience: Previous employer II", "Upload the experience letter from the employer before that.", "Skip - not applicable", True),
]


def split_education_experience(apps, schema_editor):
    Template = apps.get_model("HR", "OnboardingTemplate")
    Task = apps.get_model("HR", "OnboardingTemplateTask")
    for template in Template.objects.all():
        old = list(Task.objects.filter(template=template, title=OLD_TITLE))
        if not old:
            continue
        ordered = list(Task.objects.filter(template=template).order_by("order", "id"))
        new_order = []
        for task in ordered:
            if task.title != OLD_TITLE:
                new_order.append(task)
                continue
            base = dict(
                template=template, category="documents", responsible="employee",
                due_after_days=max(task.due_after_days, 5), required=True, requires_upload=True,
                requires_approval=True, approver="hr_manager", verifier="hr_recruiter", skippable=True,
            )
            for title, desc, skip_label, fresher in EDUCATION + EXPERIENCE:
                new_order.append(Task(title=title, description=desc, skip_label=skip_label,
                                      skip_if_fresher=fresher, order=0, **base))
        old_ids = [t.pk for t in old]
        Task.objects.filter(pk__in=old_ids).delete()
        for index, task in enumerate(new_order, start=1):
            task.order = index
            task.save()


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("HR", "0005_onboardingtask_submission_count"),
    ]

    operations = [
        migrations.AddField(
            model_name="employee", name="is_fresher",
            field=models.BooleanField(
                default=False, verbose_name="Fresher (no previous experience)",
                help_text="Experience-document steps are skipped automatically for freshers."),
        ),
        migrations.AlterField(
            model_name="onboardingtemplatetask", name="approver",
            field=models.CharField(
                choices=[("hr", "HR"), ("hr_manager", "HR Manager"), ("manager", "Reporting manager"), ("admin", "Super Admin")],
                default="hr", max_length=16, verbose_name="Confirmed by",
                help_text="Final confirmation (for example the HR Manager)."),
        ),
        migrations.AlterField(
            model_name="onboardingtemplatetask", name="requires_approval",
            field=models.BooleanField(default=False, help_text="Completion must be confirmed before it counts."),
        ),
        migrations.AddField(
            model_name="onboardingtemplatetask", name="verifier",
            field=models.CharField(
                blank=True, default="", max_length=16, verbose_name="Verified by",
                choices=[("", "No separate verification"), ("hr_recruiter", "HR Recruiter"), ("hr", "HR"),
                         ("manager", "Reporting manager"), ("admin", "Super Admin")],
                help_text="Optional first check before confirmation (for example the HR Recruiter)."),
        ),
        migrations.AddField(
            model_name="onboardingtemplatetask", name="skippable",
            field=models.BooleanField(default=False, verbose_name="Employee can skip",
                                      help_text="Shows a Skip button to the employee."),
        ),
        migrations.AddField(
            model_name="onboardingtemplatetask", name="skip_label",
            field=models.CharField(blank=True, max_length=60, help_text='Button text, e.g. "Skip - not applicable".'),
        ),
        migrations.AddField(
            model_name="onboardingtemplatetask", name="skip_if_fresher",
            field=models.BooleanField(default=False, verbose_name="Skip automatically for freshers",
                                      help_text="Used for experience documents when the candidate has no previous job."),
        ),
        migrations.AlterField(
            model_name="onboardingtask", name="approver",
            field=models.CharField(
                choices=[("hr", "HR"), ("hr_manager", "HR Manager"), ("manager", "Reporting manager"), ("admin", "Super Admin")],
                default="hr", max_length=16),
        ),
        migrations.AlterField(
            model_name="onboardingtask", name="status",
            field=models.CharField(
                choices=[("pending", "Pending"), ("submitted", "Awaiting verification"),
                         ("verified", "Verified - awaiting confirmation"), ("done", "Done"), ("skipped", "Skipped")],
                db_index=True, default="pending", max_length=10),
        ),
        migrations.AddField(
            model_name="onboardingtask", name="verifier",
            field=models.CharField(
                blank=True, default="", max_length=16,
                choices=[("", "No separate verification"), ("hr_recruiter", "HR Recruiter"), ("hr", "HR"),
                         ("manager", "Reporting manager"), ("admin", "Super Admin")]),
        ),
        migrations.AddField(
            model_name="onboardingtask", name="verified_by",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                                    related_name="+", to=settings.AUTH_USER_MODEL),
        ),
        migrations.AddField(model_name="onboardingtask", name="verified_at",
                            field=models.DateTimeField(blank=True, null=True)),
        migrations.AddField(model_name="onboardingtask", name="skippable",
                            field=models.BooleanField(default=False)),
        migrations.AddField(model_name="onboardingtask", name="skip_label",
                            field=models.CharField(blank=True, max_length=60)),
        migrations.AddField(model_name="onboardingtask", name="skip_if_fresher",
                            field=models.BooleanField(default=False)),
        migrations.RunPython(split_education_experience, migrations.RunPython.noop),
    ]
