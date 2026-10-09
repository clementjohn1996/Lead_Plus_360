from django.db import migrations, models

def seed_delivery_kpis(apps, schema_editor):
    KPI = apps.get_model("Performance", "KPI")
    defaults = [
        ("Delivery work completed", "work_completed", "", 3, 5),
        ("Delivery work on time", "work_on_time_pct", "%", 2, 90),
        ("Delivery completion rate", "work_completion_rate", "%", 2, 90),
    ]
    for name, key, unit, weight, target in defaults:
        KPI.objects.get_or_create(
            name=name,
            defaults={"auto_key": key, "unit": unit, "weight": weight, "default_target": target},
        )


class Migration(migrations.Migration):
    dependencies = [("Performance", "0005_tv_posters")]
    operations = [
        migrations.AlterField(
            model_name="kpi", name="auto_key",
            field=models.CharField(
                blank=True, max_length=30,
                choices=[
                    ("","Manual entry"),("leads_created","Leads created"),("leads_won","Leads won"),
                    ("revenue_won","Revenue won"),("activities_logged","CRM activities logged"),
                    ("tasks_completed","Tasks completed"),("tasks_on_time_pct","Tasks completed on time (%)"),
                    ("followups_completed","Follow-ups completed"),("handovers_accepted","Project handovers accepted"),
                    ("work_assigned","Delivery assignments received"),("work_completed","Delivery assignments completed"),
                    ("work_on_time_pct","Delivery work completed on time (%)"),
                    ("work_completion_rate","Delivery assignment completion rate (%)"),
                    ("attendance_rate","Attendance rate (%)"),("punctuality_pct","Punctuality (%)")
                ],
                help_text="Computed automatically from system data when set."
            ),
        ),
        migrations.RunPython(seed_delivery_kpis, migrations.RunPython.noop),
    ]
