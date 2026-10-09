from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth import get_user_model
from Control.models import Role


class Command(BaseCommand):
    help = "Create or reset a LeadPlus360 administrator account in the active database."

    def add_arguments(self, parser):
        parser.add_argument("--username", default="admin")
        parser.add_argument("--password", default="Admin@12345")
        parser.add_argument("--email", default="admin@leadplus360.local")

    def handle(self, *args, **options):
        username = options["username"].strip()
        password = options["password"]
        email = options["email"].strip()
        if len(password) < 8:
            raise CommandError("Password must contain at least 8 characters.")
        if not username:
            raise CommandError("Username cannot be empty.")

        User = get_user_model()
        user, created = User.objects.get_or_create(
            username=username,
            defaults={"email": email},
        )
        user.email = email
        user.is_active = True
        user.is_staff = True
        user.is_superuser = True
        user.set_password(password)
        user.save()

        # Ensure the administrator has the built-in Super Admin role.
        role = Role.objects.filter(name="super_admin", is_active=True).first()
        if role:
            profile = user.profile
            profile.role = role
            profile.save(update_fields=["role"])

        action = "Created" if created else "Reset"
        self.stdout.write(self.style.SUCCESS(f"{action} administrator: {username}"))
        self.stdout.write(f"Login URL: /login/")
        self.stdout.write(f"Username: {username}")
        self.stdout.write(f"Password: {password}")
