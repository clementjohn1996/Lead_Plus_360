from django.contrib.auth.models import User

from Control.models import Role, UserProfile
from HR.models import Employee


def make_user(name, role=None, superuser=False):
    user = User.objects.create_user(name, password="pw-12345-x", is_superuser=superuser, is_staff=superuser)
    if role:
        profile, _ = UserProfile.objects.get_or_create(user=user)
        profile.role = Role.objects.get(name=role)
        profile.save()
    Employee.objects.get_or_create(user=user, defaults={"status": "active"})
    return User.objects.get(pk=user.pk)
