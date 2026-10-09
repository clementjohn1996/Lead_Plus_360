"""Non-demo organisation defaults used by setup and employee creation."""

from .models import Role


STANDARD_ROLES = (
    dict(name="super_admin", label="Super Admin", level=1, is_system=True, is_privileged=True,
         is_super_admin=True, can_use_crm=True, sees_all_leads=True, sees_team_leads=True,
         can_manage_team=True, can_manage_hr=True),
    dict(name="management", label="Management", level=2, is_system=True, can_use_crm=True,
         sees_all_leads=True, can_manage_team=True, can_manage_hr=True, is_privileged=True),
    dict(name="hr", label="HR Manager", level=3, is_system=True, can_manage_team=True,
         can_manage_hr=True),
    dict(name="project_manager", label="Project Manager", level=4, is_system=True,
         can_manage_team=True),
    dict(name="bd_manager", label="Business Development Manager", level=4, is_system=True,
         can_use_crm=True, sees_all_leads=True, can_manage_team=True),
    dict(name="bd_team_lead", label="Business Development Team Lead", level=5, is_system=True,
         can_use_crm=True, sees_team_leads=True, can_manage_team=True),
    dict(name="bd_executive", label="Business Development Executive", level=6, is_system=True,
         can_use_crm=True),
    dict(name="digital_marketing", label="Digital Marketing Team", level=7, is_system=True),
    dict(name="graphic_designer", label="Graphic Designer", level=7, is_system=True),
    dict(name="videographer", label="Videographer", level=7, is_system=True),
    dict(name="video_editor", label="Video Editor", level=7, is_system=True),
    dict(name="developer", label="Developer (Software / Web)", level=7, is_system=True),
)


def ensure_standard_roles():
    """Restore only built-in role definitions; never creates users or demo data."""
    roles = []
    for definition in STANDARD_ROLES:
        values = definition.copy()
        name = values.pop("name")
        values.setdefault("is_active", True)
        role, _ = Role.objects.update_or_create(name=name, defaults=values)
        roles.append(role)
    from LeadManager.models import Department

    for role in roles:
        Department.objects.update_or_create(
            name=role.label,
            defaults={"description": role.description},
        )
    return roles
