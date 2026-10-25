# AGENTS.md

Verification commands (activate with `.\venv\Scripts\activate`):

```bash
python manage.py check
python manage.py makemigrations --check --dry-run
python manage.py test
python manage.py runserver
```

Apps: `config/` (settings, urls), `Control/` (roles, login, home), `LeadManager/` (CRM), `HR/`, `Attendance/`, `Performance/` (KPIs + TV).

Notes: Django 5.x `{% if %}` needs whitespace around `==`. Roles come from `UserProfile.role`; helpers live in `Control/permissions.py`.