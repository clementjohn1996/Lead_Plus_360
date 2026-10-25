from django.core.management.base import BaseCommand
from Control.org_defaults import ensure_standard_roles

class Command(BaseCommand):
    help = 'Ensure all standard LeadPlus360 organisational roles exist with their default capabilities.'

    def handle(self, *args, **options):
        ensure_standard_roles()
        self.stdout.write(self.style.SUCCESS('LeadPlus360 organisational roles and capabilities are ready.'))
