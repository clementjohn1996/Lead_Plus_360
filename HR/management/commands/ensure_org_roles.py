from django.core.management.base import BaseCommand
from Control.models import Role

# name, label, level, capability flags
ROLES = [
    dict(name='super_admin', label='Super Admin', level=1, is_system=True, is_privileged=True, is_super_admin=True, can_use_crm=True, sees_all_leads=True, sees_team_leads=True, can_manage_team=True, can_manage_hr=True),
    dict(name='management', label='Management', level=2, is_system=True, can_use_crm=True, sees_all_leads=True, sees_team_leads=True, can_manage_team=True),
    dict(name='hr', label='HR Manager', level=3, is_system=True, can_use_crm=False, can_manage_team=True, can_manage_hr=True),
    dict(name='project_manager', label='Project Manager', level=4, is_system=True, can_manage_team=True),
    dict(name='bd_manager', label='Business Development Manager', level=4, is_system=True, can_use_crm=True, sees_team_leads=True, can_manage_team=True),
    dict(name='bd_team_lead', label='Business Development Team Lead', level=5, is_system=True, can_use_crm=True, sees_team_leads=True, can_manage_team=True),
    dict(name='bd_executive', label='Business Development Executive', level=6, is_system=True, can_use_crm=True),
    dict(name='digital_marketing', label='Digital Marketing Team', level=7, is_system=True),
    dict(name='graphic_designer', label='Graphic Designer', level=7, is_system=True),
    dict(name='videographer', label='Videographer', level=7, is_system=True),
    dict(name='video_editor', label='Video Editor', level=7, is_system=True),
    dict(name='developer', label='Developer (Software / Web)', level=7, is_system=True),
]

class Command(BaseCommand):
    help = 'Ensure all standard LeadPlus360 organisational roles exist with their default capabilities.'

    def handle(self, *args, **options):
        for data in ROLES:
            name = data.pop('name')
            role, _ = Role.objects.get_or_create(name=name, defaults=data)
            for key, value in data.items():
                setattr(role, key, value)
            role.save()
            data['name'] = name
        self.stdout.write(self.style.SUCCESS('LeadPlus360 organisational roles and capabilities are ready.'))
