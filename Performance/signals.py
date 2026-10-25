from django.db.models.signals import post_save
from django.dispatch import receiver

from LeadManager.models import Deal, Lead


@receiver(post_save, sender=Lead)
def lead_changed(sender, instance, **kwargs):
    from . import bde
    bde.recalc_for_lead(instance)


@receiver(post_save, sender=Deal)
def deal_changed(sender, instance, **kwargs):
    from . import bde
    bde.recalc_for_lead(instance.lead)
