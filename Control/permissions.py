"""Role helpers shared by every app. Roles live on Control.UserProfile.role.

Hierarchy: Super Admin > Management > HR > Project Manager / BD Manager >
BD Team Lead > BD Executive > delivery and creative teams."""
from functools import wraps

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied

def role_of(user):
    if not getattr(user, "is_authenticated", False):
        return None
    profile = getattr(user, "profile", None)
    return profile.role if profile and profile.role_id and profile.role.is_active else None


def role_name(user):
    role = role_of(user)
    return role.name if role else ""


def has_flag(user, flag):
    """Superusers pass every check; everyone else needs the capability on their role."""
    if not getattr(user, "is_authenticated", False):
        return False
    if user.is_superuser:
        return True
    role = role_of(user)
    return bool(role and getattr(role, flag))


def is_admin(user):
    return has_flag(user, "is_super_admin")


def is_hr(user):
    return has_flag(user, "can_manage_hr")


def can_use_crm(user):
    return has_flag(user, "can_use_crm")


def can_manage_team(user):
    return has_flag(user, "can_manage_team")


def sees_all_leads(user):
    return has_flag(user, "sees_all_leads")


def sees_team_leads(user):
    return has_flag(user, "sees_team_leads")


def assignable_roles(user):
    """Roles the acting user may grant. Privileged roles are Super Admin only."""
    from .models import Role

    qs = Role.objects.filter(is_active=True)
    return qs if is_admin(user) else qs.filter(is_privileged=False, is_super_admin=False)


def permission_required(check):
    """Login + custom permission check; raises 403 on failure."""

    def decorator(view):
        @wraps(view)
        @login_required
        def wrapper(request, *args, **kwargs):
            if not check(request.user):
                raise PermissionDenied
            return view(request, *args, **kwargs)

        return wrapper

    return decorator


hr_required = permission_required(is_hr)
crm_required = permission_required(can_use_crm)
manager_required = permission_required(can_manage_team)
admin_required = permission_required(is_admin)
