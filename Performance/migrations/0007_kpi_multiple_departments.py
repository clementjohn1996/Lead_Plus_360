from django.db import migrations, models


def copy_department(apps, schema_editor):
    KPI = apps.get_model("Performance", "KPI")
    for kpi in KPI.objects.exclude(department__isnull=True):
        kpi.departments.add(kpi.department_id)


def restore_department(apps, schema_editor):
    KPI = apps.get_model("Performance", "KPI")
    for kpi in KPI.objects.all():
        first = kpi.departments.first()
        if first:
            kpi.department_id = first.pk
            kpi.save(update_fields=["department"])


class Migration(migrations.Migration):
    dependencies = [
        ("LeadManager", "0007_seed_core_departments"),
        ("Performance", "0006_delivery_kpis"),
    ]

    operations = [
        migrations.AddField(
            model_name="kpi",
            name="departments",
            field=models.ManyToManyField(
                blank=True, related_name="applicable_kpis", to="LeadManager.department",
                help_text="Tick every department this KPI applies to. Leave all unticked to apply it to every department.",
            ),
        ),
        migrations.RunPython(copy_department, restore_department),
        migrations.RemoveField(model_name="kpi", name="department"),
    ]
