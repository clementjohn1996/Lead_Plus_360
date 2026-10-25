from django.core.management.base import BaseCommand

from Outreach import services


class Command(BaseCommand):
    help = "Send approved outreach emails that are due (run every 15 minutes from a scheduler)."

    def handle(self, *args, **options):
        sent, reason = services.send_due()
        self.stdout.write(f"Sent {sent} email(s). {reason}")
