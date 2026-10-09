from django.db import migrations, models

RENAMES = {
    "director": ("super_admin", "Super Admin"),
    "bds_manager": ("bd_manager", "Business Development Manager"),
    "bds_exec": ("bd_executive", "Business Development Executive"),
    "delivery_lead": ("project_manager", "Project Manager"),
}
NEW = [
    ("super_admin", "Super Admin", "Complete rights over every module, roles and settings."),
    ("management", "Management", "Company-wide visibility: CRM, HR, attendance and performance."),
    ("hr", "HR Manager", "Onboarding, attendance and employee records."),
    ("project_manager", "Project Manager", "Delivery oversight, handovers and team performance."),
    ("bd_manager", "Business Development Manager", "All leads, pipeline and BD team performance."),
    ("bd_team_lead", "Business Development Team Lead", "Own and team leads; leads the BD executives."),
    ("bd_executive", "Business Development Executive", "Own leads and tasks."),
    ("digital_marketing", "Digital Marketing Team", "Self-service."),
    ("graphic_designer", "Graphic Designer", "Self-service."),
    ("videographer", "Videographer", "Self-service."),
    ("video_editor", "Video Editor", "Self-service."),
    ("developer", "Developer (Software / Web)", "Self-service."),
]


def forwards(apps, schema_editor):
    Role = apps.get_model("Control", "Role")
    for old, (new, label) in RENAMES.items():
        Role.objects.filter(name=old).update(name=new, label=label)
    for name, label, desc in NEW:
        role, created = Role.objects.get_or_create(name=name, defaults={"label": label, "description": desc})
        if not created:
            role.label, role.description = label, desc
            role.save()
    # The generic "employee" role is replaced by the specific team roles.
    Role.objects.filter(name="employee").update(is_active=False, label="General staff (legacy)")


class Migration(migrations.Migration):
    dependencies = [("Control", "0003_hr_employee_roles")]
    operations = [
        migrations.AlterField(
            model_name="role",
            name="name",
            field=models.CharField(max_length=20, unique=True, choices=[
                ("super_admin", "Super Admin"), ("management", "Management"), ("hr", "HR Manager"),
                ("project_manager", "Project Manager"), ("bd_manager", "Business Development Manager"),
                ("bd_team_lead", "Business Development Team Lead"),
                ("bd_executive", "Business Development Executive"),
                ("digital_marketing", "Digital Marketing Team"), ("graphic_designer", "Graphic Designer"),
                ("videographer", "Videographer"), ("video_editor", "Video Editor"),
                ("developer", "Developer (Software / Web)")]),
        ),
        migrations.RunPython(forwards, migrations.RunPython.noop),
    ]
