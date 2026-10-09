from django.db import migrations


DEPARTMENTS = [
    ("Management", "Company leadership, strategy and approvals."),
    ("Human Resources", "People, recruitment, onboarding and employee administration."),
    ("Business Development", "BDE and BDM lead generation, qualification and sales."),
    ("Project Management", "Project planning, coordination, delivery and client communication."),
    ("Web & Software Development", "Websites, web applications, software and technical development."),
    ("Graphic Design", "Branding, graphics, social creatives and visual design."),
    ("Video Production", "Videography, filming, production and post-production."),
    ("Digital Marketing", "SEO, social media, paid advertising and digital campaigns."),
    ("Quality Assurance", "Testing, review and delivery quality control."),
]

def seed_departments(apps, schema_editor):
    Department = apps.get_model("LeadManager", "Department")
    for name, description in DEPARTMENTS:
        Department.objects.get_or_create(name=name, defaults={"description": description})

class Migration(migrations.Migration):
    dependencies = [("LeadManager", "0006_deal_contract_start_deal_renewal_date_and_more")]
    operations = [migrations.RunPython(seed_departments, migrations.RunPython.noop)]
