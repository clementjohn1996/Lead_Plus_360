from django.contrib.auth.models import User
from django.core.management.base import BaseCommand

from HR.models import Employee


class Command(BaseCommand):
    help = "Create Employee records for users that do not have one."

    def handle(self, *args, **options):
        created = 0
        for user in User.objects.filter(employee__isnull=True, is_active=True):
            designation = "Director" if user.is_superuser else ""
            Employee.objects.create(user=user, designation=designation, status="active")
            created += 1
        self.stdout.write(self.style.SUCCESS(f"Created {created} employee record(s)."))