from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import FaceTemplate


@receiver(post_save, sender=FaceTemplate)
def complete_face_onboarding(sender, instance, created, **kwargs):
    if created:
        from HR.services import sync_auto_tasks

        sync_auto_tasks(instance.employee)
