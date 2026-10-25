from django.core.management.base import BaseCommand

from Outreach import profiler
from Outreach.models import OutreachSettings, Prospect


class Command(BaseCommand):
    help = "Scan the websites of prospects that have never been scanned."

    def add_arguments(self, parser):
        parser.add_argument("--limit", type=int, default=30)

    def handle(self, *args, **options):
        confirmed = OutreachSettings.get_solo().confirmed_signals
        if not confirmed:
            self.stdout.write("No signals confirmed. Confirm some under Growth engine > Signals & settings.")
            return
        for prospect in Prospect.objects.filter(last_scanned__isnull=True)[: options["limit"]]:
            self.stdout.write(f"{prospect.company}: {profiler.scan_prospect(prospect, confirmed)}")
