from datetime import timedelta
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone
from LeadManager.models import Lead
from .models import WorkItem

@receiver(post_save, sender=Lead)
def create_delivery_work_on_win(sender, instance, created, **kwargs):
    if instance.stage != "won":
        return
    services = list(instance.services.all())
    if not services and instance.service_id:
        services = [instance.service]
    for service in services:
        department = service.departments.order_by("id").first()
        if not department:
            continue
        handover = instance.handovers.filter(service=service).order_by("-id").first()
        due = handover.target_delivery_date if handover and handover.target_delivery_date else timezone.localdate() + timedelta(days=7)
        WorkItem.objects.get_or_create(
            lead=instance, service=service,
            defaults={
                "handover": handover,
                "title": f"{service.name} — {instance.company or instance.name}",
                "description": instance.notes or "",
                "department": department,
                "bde": instance.owner,
                "bdm": instance.manager,
                "project_manager": department.head,
                "created_by": instance.owner,
                "priority": instance.priority if instance.priority in {"low","medium","high","urgent"} else "medium",
                "due_date": due,
            },
        )
