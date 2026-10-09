from django.db import migrations, models

ROLES = [
    ("hr", "HR Manager", "Onboarding, attendance and employee records."),
    ("employee", "Employee", "Self-service: attendance, onboarding, own performance."),
]


def seed_roles(apps, schema_editor):
    Role = apps.get_model("Control", "Role")
    for name, label, description in ROLES:
        Role.objects.get_or_create(name=name, defaults={"label": label, "description": description})


class Migration(migrations.Migration):

    dependencies = [
        ("Control", "0002_alter_userprofile_options_userprofile_phone_and_more"),
    ]

    operations = [
        migrations.AlterField(
            model_name="role",
            name="name",
            field=models.CharField(
                choices=[
                    ("director", "Admin / Director"),
                    ("hr", "HR Manager"),
                    ("bds_manager", "BDS Manager"),
                    ("bds_exec", "BDS Executive"),
                    ("delivery_lead", "Delivery / Production Lead"),
                    ("employee", "Employee"),
                ],
                max_length=20,
                unique=True,
            ),
        ),
        migrations.RunPython(seed_roles, migrations.RunPython.noop),
    ]
