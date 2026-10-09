from datetime import timedelta
from django.core.management.base import BaseCommand
from django.utils import timezone
from LeadManager.models import Lead
from Delivery.models import WorkItem

class Command(BaseCommand):
    help = "Create delivery workflow records for existing won leads."

    def handle(self, *args, **options):
        created = 0
        for lead in Lead.objects.filter(stage="won").prefetch_related("services","handovers"):
            services = list(lead.services.all())
            if not services and lead.service_id:
                services = [lead.service]
            for service in services:
                department = service.departments.order_by("id").first()
                if not department:
                    continue
                handover = lead.handovers.filter(service=service).order_by("-id").first()
                due = handover.target_delivery_date if handover and handover.target_delivery_date else timezone.localdate() + timedelta(days=7)
                _, was_created = WorkItem.objects.get_or_create(
                    lead=lead, service=service,
                    defaults={
                        "handover": handover,
                        "title": f"{service.name} — {lead.company or lead.name}",
                        "description": lead.notes or "",
                        "department": department,
                        "bde": lead.owner,
                        "bdm": lead.manager,
                        "project_manager": department.head,
                        "created_by": lead.owner,
                        "priority": lead.priority if lead.priority in {"low","medium","high","urgent"} else "medium",
                        "due_date": due,
                    },
                )
                created += int(was_created)
        self.stdout.write(self.style.SUCCESS(f"Delivery workflow sync complete. Created {created} work item(s)."))
