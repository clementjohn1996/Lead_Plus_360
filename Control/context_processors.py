from django.conf import settings

from .models import OrganizationSettings
from .navigation import build_navigation
from .permissions import (
    can_manage_accounts, can_manage_team, can_use_crm, can_use_outreach, is_admin, is_hr,
)


def navigation(request):
    """Expose role-based navigation to every template."""
    product = {"product_name": getattr(settings, "PRODUCT_NAME", "GrowthForge 360")}
    user = request.user
    organization = OrganizationSettings.get_solo()
    if not user.is_authenticated:
        return {"organization": organization, **product}
    profile = getattr(user, "profile", None)
    url_name = getattr(getattr(request, "resolver_match", None), "url_name", "") or ""
    return {
        "nav": {
            "crm": can_use_crm(user),
            "outreach": can_use_outreach(user),
            "accounts": can_manage_accounts(user),
            "hr": is_hr(user),
            "admin": is_admin(user),
            "manager": can_manage_team(user),
            "staff": user.is_staff,
            "role_label": (profile.role.label if profile and profile.role_id else (
                "Administrator" if user.is_superuser else "Team member")),
            "employee": getattr(user, "employee", None),
        },
        "nav_groups": build_navigation(user, url_name),
        "organization": organization,
        **product,
    }
