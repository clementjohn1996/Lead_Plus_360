from django.db import migrations


def seed_roles_and_departments(apps, schema_editor):
    Role = apps.get_model("Control", "Role")
    Department = apps.get_model("LeadManager", "Department")
    Service = apps.get_model("LeadManager", "Service")

    # Create default roles
    roles = [
        ("director", "Admin / Director", "Full system access, P&L reporting, conversion metrics."),
        ("bds_manager", "BDS Manager", "Lead assignment, team reallocation, performance dashboards, SLA monitoring."),
        ("bds_exec", "BDS Executive", "View and edit self-assigned leads, log communications, set reminders."),
        ("delivery_lead", "Delivery / Production Lead", "Read-only visibility into accepted handovers."),
    ]
    for name, label, desc in roles:
        Role.objects.get_or_create(
            name=name, defaults={"label": label, "description": desc}
        )

    # Create default departments
    departments = [
        ("Web Development", "Custom sites, CMS, e-commerce builds"),
        ("SEO", "Search Engine Optimization & Local SEO"),
        ("Meta Ads", "Facebook / Instagram lead-gen & conversion campaigns"),
        ("Google Ads", "Search, Display, Performance Max, YouTube"),
        ("Media Production", "Commercial video shoots, corporate photo shoots, product stills"),
        ("Creative & Branding", "Social media content, branding, design assets"),
    ]
    for name, desc in departments:
        Department.objects.get_or_create(name=name, defaults={"description": desc})

    # Assign services to departments
    dept_service_map = {
        "Web Development": ["Web & App Development"],
        "SEO": ["Search Engine Optimization"],
        "Meta Ads": ["Meta Ads"],
        "Google Ads": ["Google Ads"],
        "Media Production": ["Media Production"],
        "Creative & Branding": ["Social Media Management & Branding"],
    }
    for dept_name, service_names in dept_service_map.items():
        dept = Department.objects.filter(name=dept_name).first()
        if not dept:
            continue
        for svc_name in service_names:
            svc = Service.objects.filter(name=svc_name).first()
            if svc and not dept.services.filter(pk=svc.pk).exists():
                dept.services.add(svc)


class Migration(migrations.Migration):

    dependencies = [
        ("LeadManager", "0004_populate_slugs"),
        ("Control", "0002_alter_userprofile_options_userprofile_phone_and_more"),
    ]

    operations = [
        migrations.RunPython(seed_roles_and_departments, migrations.RunPython.noop),
    ]
