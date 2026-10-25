from django.core.management.base import BaseCommand
from LeadManager.models import Department

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

class Command(BaseCommand):
    help = "Create the standard LeadPlus360 departments."
    def handle(self, *args, **options):
        for name, description in DEPARTMENTS:
            Department.objects.update_or_create(name=name, defaults={"description": description})
        self.stdout.write(self.style.SUCCESS("LeadPlus360 departments are ready."))
