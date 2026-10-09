from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import OnboardingTask


@receiver(post_save, sender=OnboardingTask)
def activate_when_onboarded(sender, instance, **kwargs):
    from .services import refresh_status

    refresh_status(instance.employee)
