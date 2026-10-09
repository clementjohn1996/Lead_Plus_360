from django.core.management.base import BaseCommand

from Performance import bde


class Command(BaseCommand):
    help = "Finalise completed months and evaluate every BDE (PIP / appraisal / alerts). Schedule monthly."

    def handle(self, *args, **options):
        count = bde.run_monthly()
        self.stdout.write(self.style.SUCCESS(f"Calculated performance for {count} BDEs."))
