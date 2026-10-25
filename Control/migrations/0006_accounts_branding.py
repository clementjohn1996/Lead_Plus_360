from django.db import migrations, models


def enable_accounts_for_managers(apps, schema_editor):
    Role = apps.get_model("Control", "Role")
    Role.objects.filter(name__in=["super_admin", "management"]).update(can_manage_accounts=True)


class Migration(migrations.Migration):
    dependencies = [("Control", "0005_role_capabilities")]
    operations = [
        migrations.AddField(model_name="role", name="can_manage_accounts", field=models.BooleanField(default=False, help_text="Customers, invoices, payments, expenses and reports.", verbose_name="Accounts access")),
        migrations.CreateModel(name="OrganizationSettings", fields=[
            ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")), ("name", models.CharField(default="LeadPlus-360", max_length=160)),
            ("tagline", models.CharField(blank=True, max_length=200)), ("logo", models.ImageField(blank=True, null=True, upload_to="organization/")), ("primary_color", models.CharField(default="#6d4aff", max_length=7)), ("currency", models.CharField(default="INR", max_length=3)), ("tax_id", models.CharField(blank=True, max_length=80)), ("billing_email", models.EmailField(blank=True, max_length=254)), ("phone", models.CharField(blank=True, max_length=40)), ("address", models.TextField(blank=True)), ("invoice_prefix", models.CharField(default="INV", max_length=12)), ("updated_at", models.DateTimeField(auto_now=True)),
        ], options={"verbose_name": "Organization settings", "verbose_name_plural": "Organization settings"}),
        migrations.RunPython(enable_accounts_for_managers, migrations.RunPython.noop),
    ]
