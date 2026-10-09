from django.contrib.auth.models import User
from django.db import models


class Role(models.Model):
    """
    An organisational role. Roles are defined by Super Admins at runtime; what a role
    may do is controlled by the capability flags below (see Control.permissions).
    """

    name = models.SlugField(max_length=40, unique=True, help_text="Internal key, set once.")
    label = models.CharField(max_length=80)
    description = models.TextField(blank=True)
    level = models.PositiveSmallIntegerField(
        default=100, help_text="Seniority for ordering. Lower numbers are more senior."
    )
    is_active = models.BooleanField(default=True)
    is_system = models.BooleanField(default=False, help_text="Built-in role; cannot be deleted.")

    can_use_crm = models.BooleanField("Can use CRM", default=False)
    sees_all_leads = models.BooleanField("Sees every lead", default=False)
    sees_team_leads = models.BooleanField(
        "Sees leads of direct reports", default=False,
        help_text="Also sees leads owned by employees who report to this user.",
    )
    can_manage_team = models.BooleanField(
        "Team manager", default=False, help_text="Team performance views and data entry."
    )
    can_manage_hr = models.BooleanField(
        "HR access", default=False, help_text="Employees, onboarding, attendance admin, KPIs, TV displays."
    )
    can_manage_accounts = models.BooleanField(
        "Accounts access", default=False, help_text="Customers, invoices, payments, expenses and reports."
    )
    is_privileged = models.BooleanField(
        "Privileged", default=False, help_text="Only a Super Admin may assign this role."
    )
    is_super_admin = models.BooleanField(
        "Super Admin", default=False, help_text="Complete rights, including roles and workflows."
    )
    permissions = models.ManyToManyField(
        "auth.Permission",
        blank=True,
        help_text="Additional permissions granted to users with this role.",
    )

    class Meta:
        ordering = ["level", "label"]

    def __str__(self):
        return self.label


class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="profile")
    profile_picture = models.ImageField(upload_to="profile_pics/", blank=True, null=True)
    role = models.ForeignKey(
        Role,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="users",
    )
    phone = models.CharField(max_length=40, blank=True)
    team = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="team_members",
        help_text="Manager this user reports to (BDS Executive → BDS Manager).",
    )

    class Meta:
        verbose_name = "User Profile"
        verbose_name_plural = "User Profiles"

    def __str__(self):
        return self.user.username

    @property
    def role_name(self):
        return self.role.name if self.role_id else ""

    @property
    def is_hr(self):
        return bool(self.role_id and self.role.can_manage_hr)

    @property
    def is_super_admin(self):
        return bool(self.role_id and self.role.is_super_admin)


class OrganizationSettings(models.Model):
    """Singleton company identity and billing defaults shown across the workspace."""

    name = models.CharField(max_length=160, default="LeadPlus-360")
    tagline = models.CharField(max_length=200, blank=True)
    logo = models.ImageField(upload_to="organization/", blank=True, null=True)
    primary_color = models.CharField(max_length=7, default="#6d4aff")
    currency = models.CharField(max_length=3, default="INR")
    tax_id = models.CharField(max_length=80, blank=True)
    billing_email = models.EmailField(blank=True)
    phone = models.CharField(max_length=40, blank=True)
    address = models.TextField(blank=True)
    invoice_prefix = models.CharField(max_length=12, default="INV")
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Organization settings"
        verbose_name_plural = "Organization settings"

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)

    @classmethod
    def get_solo(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj
