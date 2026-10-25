from django.db import migrations
from django.utils.text import slugify


def populate_slugs(apps, schema_editor):
    Service = apps.get_model("LeadManager", "Service")
    Department = apps.get_model("LeadManager", "Department")

    for model in [Service, Department]:
        used = set()
        for obj in model.objects.filter(slug__isnull=True):
            base = slugify(obj.name)
            slug = base
            counter = 2
            while slug in used or model.objects.filter(slug=slug).exclude(pk=obj.pk).exists():
                slug = f"{base}-{counter}"
                counter += 1
            used.add(slug)
            obj.slug = slug
            obj.save(update_fields=["slug"])


class Migration(migrations.Migration):

    dependencies = [
        ("LeadManager", "0003_department_followupschedule_leadstatushistory_and_more"),
    ]

    operations = [
        migrations.RunPython(populate_slugs, migrations.RunPython.noop),
    ]
