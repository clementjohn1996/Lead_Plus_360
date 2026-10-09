from django.db import migrations

DEFAULT_KPIS = [
    ("Leads won", "leads_won", "", 3, 3),
    ("Revenue won", "revenue_won", "", 3, 100000),
    ("Tasks completed on time", "tasks_on_time_pct", "%", 2, 90),
    ("Tasks completed", "tasks_completed", "", 2, 20),
    ("Attendance", "attendance_rate", "%", 2, 95),
    ("Punctuality", "punctuality_pct", "%", 1, 90),
    ("Quality of work (manager rating)", "", "pts", 3, 80),
]


def seed(apps, schema_editor):
    KPI = apps.get_model("Performance", "KPI")
    if KPI.objects.exists():
        return
    for name, key, unit, weight, target in DEFAULT_KPIS:
        KPI.objects.create(name=name, auto_key=key, unit=unit, weight=weight, default_target=target)


class Migration(migrations.Migration):
    dependencies = [("Performance", "0001_initial")]
    operations = [migrations.RunPython(seed, migrations.RunPython.noop)]