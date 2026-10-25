from django.db import migrations

DEFAULT_TASKS = [
    ("Submit ID proof", "Upload a government-issued photo ID.", "documents", "employee", 1, True, True, ""),
    ("Submit address proof", "Upload a recent address proof.", "documents", "employee", 3, True, True, ""),
    ("Submit education & experience documents", "Upload certificates and previous experience letters.", "documents", "employee", 5, False, True, ""),
    ("Sign offer letter / contract", "HR to collect the signed copy.", "documents", "hr", 2, True, False, ""),
    ("Create email and tool accounts", "Email, chat, project tools and CRM access.", "setup", "it", 1, True, False, ""),
    ("Assign laptop and equipment", "Hand over devices and record asset tags.", "setup", "it", 1, True, False, ""),
    ("Read and accept company policies", "Code of conduct, confidentiality and leave policy.", "compliance", "employee", 3, True, False, ""),
    ("Enroll face for attendance", "Open Attendance and capture your face once.", "attendance", "employee", 1, True, False, "face_enrollment"),
    ("Meet reporting manager", "Introductions, role expectations and first-month goals.", "orientation", "manager", 2, True, False, ""),
    ("Complete orientation / training", "Company, services and tools walkthrough.", "orientation", "hr", 7, False, False, ""),
]


def seed(apps, schema_editor):
    Template = apps.get_model("HR", "OnboardingTemplate")
    Task = apps.get_model("HR", "OnboardingTemplateTask")
    template, created = Template.objects.get_or_create(name="Standard onboarding", defaults={"is_default": True})
    if not created:
        return
    for order, (title, desc, cat, resp, days, required, upload, key) in enumerate(DEFAULT_TASKS, start=1):
        Task.objects.create(template=template, title=title, description=desc, category=cat, responsible=resp,
                            due_after_days=days, required=required, requires_upload=upload, auto_key=key, order=order)


class Migration(migrations.Migration):
    dependencies = [("HR", "0001_initial")]
    operations = [migrations.RunPython(seed, migrations.RunPython.noop)]