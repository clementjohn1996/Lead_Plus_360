from django.db import migrations, models


def apply_defaults(apps, schema_editor):
    Role = apps.get_model("Control", "Role")
    for name in ("super_admin", "management", "bd_manager", "bd_team_lead", "bd_executive"):
        Role.objects.filter(name=name).update(can_use_outreach=True)
    Role.objects.filter(is_super_admin=True).update(can_use_outreach=True)
    # HR Recruiter verifies candidate documents (see HR onboarding workflow).
    Role.objects.get_or_create(
        name="hr_recruiter",
        defaults=dict(
            label="HR Recruiter", level=4, is_system=True, can_manage_hr=True, is_active=True,
            description="Verifies candidate education and experience documents during onboarding.",
        ),
    )
    Org = apps.get_model("Control", "OrganizationSettings")
    Org.objects.filter(name="LeadPlus-360").update(name="GrowthForge 360")


class Migration(migrations.Migration):
    dependencies = [("Control", "0006_accounts_branding")]

    operations = [
        migrations.AddField(
            model_name="role",
            name="can_use_outreach",
            field=models.BooleanField(
                default=False, verbose_name="Can use Outreach",
                help_text="Prospecting, website signals, campaigns and the email approval desk.",
            ),
        ),
        migrations.AlterField(
            model_name="organizationsettings",
            name="name",
            field=models.CharField(default="GrowthForge 360", max_length=160),
        ),
        migrations.RunPython(apply_defaults, migrations.RunPython.noop),
    ]
