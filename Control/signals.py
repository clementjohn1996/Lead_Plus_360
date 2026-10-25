# Control/signals.py
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth.models import User
from .models import UserProfile

@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if created and not hasattr(instance, 'profile'):
        UserProfile.objects.create(user=instance)


@receiver(post_save, sender=UserProfile)
def sync_super_admin(sender, instance, **kwargs):
    """The Super Admin role carries Django superuser rights (admin site, all permissions)."""
    user = instance.user
    if instance.is_super_admin:
        if not (user.is_superuser and user.is_staff):
            User.objects.filter(pk=user.pk).update(is_superuser=True, is_staff=True)
    elif instance.role_id and user.is_superuser:
        if User.objects.filter(is_superuser=True, is_active=True).exclude(pk=user.pk).exists():
            User.objects.filter(pk=user.pk).update(is_superuser=False, is_staff=False)
