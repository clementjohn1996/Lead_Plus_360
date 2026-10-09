from .permissions import can_manage_team, can_use_crm, is_admin, is_hr


def navigation(request):
    """Expose role-based navigation flags to every template."""
    user = request.user
    if not user.is_authenticated:
        return {}
    profile = getattr(user, "profile", None)
    return {
        "nav": {
            "crm": can_use_crm(user),
            "hr": is_hr(user),
            "admin": is_admin(user),
            "manager": can_manage_team(user),
            "staff": user.is_staff,
            "role_label": (profile.role.label if profile and profile.role_id else ("Administrator" if user.is_superuser else "Team member")),
            "employee": getattr(user, "employee", None),
        }
    }
