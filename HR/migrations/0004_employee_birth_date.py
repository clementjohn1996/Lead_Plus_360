from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("HR", "0003_workflow_roles_approvals")]

    operations = [
        migrations.AddField(
            model_name="employee",
            name="date_of_birth",
            field=models.DateField(blank=True, help_text="Used for employee birthday recognition on TV displays.", null=True),
        ),
    ]
