from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import User
from django.utils import timezone
from django.utils.html import format_html

from .models import (
    Activity,
    Deal,
    Department,
    FollowUpSchedule,
    Lead,
    LeadNote,
    LeadSource,
    LeadStatusHistory,
    LostReasonLog,
    Meeting,
    Proposal,
    Reminder,
    Service,
    ServiceHandover,
    Task,
)


# ============================================================
# LEAD SOURCE ADMIN
# ============================================================

@admin.register(LeadSource)
class LeadSourceAdmin(admin.ModelAdmin):
    list_display = ("name", "icon", "is_active", "lead_count", "created_at")
    list_filter = ("is_active", "created_at")
    search_fields = ("name",)
    ordering = ("name",)
    list_per_page = 25

    @admin.display(description="Leads")
    def lead_count(self, obj):
        return obj.leads.count()


# ============================================================
# SERVICE ADMIN
# ============================================================

@admin.register(Service)
class ServiceAdmin(admin.ModelAdmin):
    list_display = ("name", "category", "default_rate", "is_active", "department_count", "created_at")
    list_filter = ("category", "is_active", "created_at")
    search_fields = ("name", "description")
    list_per_page = 25
    ordering = ("name",)

    @admin.display(description="Departments")
    def department_count(self, obj):
        return obj.departments.count()


# ============================================================
# DEPARTMENT ADMIN
# ============================================================

@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    list_display = ("name", "head", "service_count", "created_at")
    list_filter = ("created_at",)
    search_fields = ("name", "description")
    filter_horizontal = ("services",)
    list_per_page = 25

    @admin.display(description="Services")
    def service_count(self, obj):
        return obj.services.count()


# ============================================================
# LEAD STATUS HISTORY (inline)
# ============================================================

class LeadStatusHistoryInline(admin.TabularInline):
    model = LeadStatusHistory
    extra = 0
    fields = ("from_stage", "to_stage", "changed_by", "changed_at", "reason")
    readonly_fields = ("from_stage", "to_stage", "changed_by", "changed_at", "reason")
    can_delete = False

    def has_add_permission(self, request, obj=None):
        return False

    def get_queryset(self, request, *args, **kwargs):
        return super().get_queryset(request, *args, **kwargs).select_related("changed_by")


# ============================================================
# ACTIVITY (inline)
# ============================================================

class ActivityInline(admin.TabularInline):
    model = Activity
    extra = 0
    fields = ("activity_type", "outcome", "subject", "body", "completed", "due_at", "created_by", "created_at")
    readonly_fields = ("created_at",)
    autocomplete_fields = ("created_by",)
    can_delete = False


# ============================================================
# FOLLOW-UP SCHEDULE (inline)
# ============================================================

class FollowUpInline(admin.TabularInline):
    model = FollowUpSchedule
    extra = 0
    fields = (
        "title",
        "due_at",
        "status",
        "snooze_until",
        "notification_sent",
        "assigned_to",
        "created_at",
    )
    readonly_fields = ("created_at",)
    autocomplete_fields = ("assigned_to",)
    can_delete = False


# ============================================================
# SERVICE HANDOVER (inline)
# ============================================================

class ServiceHandoverInline(admin.TabularInline):
    model = ServiceHandover
    extra = 0
    fields = (
        "service",
        "department",
        "target_deliverable",
        "target_delivery_date",
        "approved_quote",
        "billing_type",
        "status",
        "accepted_by",
        "accepted_at",
    )
    autocomplete_fields = ("service", "department", "accepted_by")
    can_delete = False


# ============================================================
# LOST REASON LOG (inline)
# ============================================================

class LostReasonLogInline(admin.TabularInline):
    model = LostReasonLog
    extra = 0
    fields = ("reason", "notes", "logged_by", "logged_at")
    readonly_fields = ("logged_at",)
    autocomplete_fields = ("logged_by",)
    can_delete = False


# ============================================================
# MEETING INLINE
# ============================================================

class MeetingInline(admin.TabularInline):
    model = Meeting
    extra = 0
    fields = ("title", "meeting_type", "scheduled_at", "duration_minutes", "status")
    readonly_fields = ("scheduled_at",)
    autocomplete_fields = ()
    can_delete = False

    def has_add_permission(self, request, obj=None):
        return False


# ============================================================
# REMINDER INLINE
# ============================================================

class ReminderInline(admin.TabularInline):
    model = Reminder
    extra = 0
    fields = ("title", "reminder_type", "due_at", "status", "notification_sent")
    readonly_fields = ("title", "reminder_type", "due_at", "status", "notification_sent")
    can_delete = False

    def has_add_permission(self, request, obj=None):
        return False


# ============================================================
# LEAD ADMIN
# ============================================================

@admin.register(Lead)
class LeadAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "name",
        "company",
        "email",
        "phone",
        "status_badge",
        "temperature_badge",
        "priority_badge",
        "deal_value_display",
        "services_list",
        "owner",
        "manager",
        "next_follow_up",
        "created_at",
    )
    list_filter = (
        "stage",
        "temperature",
        "priority",
        "source",
        "services",
        "owner",
        "manager",
        "budget_tier",
        "billing_type",
        "created_at",
        "next_follow_up",
    )
    search_fields = (
        "id",
        "name",
        "company",
        "email",
        "phone",
        "website",
        "city",
        "state",
        "country",
        "designation",
        "industry",
    )
    autocomplete_fields = ("source", "services", "owner", "manager")
    filter_horizontal = ("services",)
    readonly_fields = ("created_at", "updated_at")
    list_per_page = 50
    date_hierarchy = "created_at"

    inlines = [
        LeadStatusHistoryInline,
        ActivityInline,
        FollowUpInline,
        ServiceHandoverInline,
        LostReasonLogInline,
        MeetingInline,
        ReminderInline,
    ]

    fieldsets = (
        (
            "Lead Information",
            {
                "fields": (
                    "name",
                    "company",
                    "designation",
                    "industry",
                    "email",
                    "phone",
                    "alternate_phone",
                    "website",
                    "linkedin",
                    "facebook",
                    "instagram",
                )
            },
        ),
        (
            "Location",
            {
                "fields": (
                    "city",
                    "state",
                    "country",
                )
            },
        ),
        (
            "Lead Qualification",
            {
                "fields": (
                    "source",
                    "services",
                    "stage",
                    "temperature",
                    "priority",
                    "budget_tier",
                    "billing_type",
                    "estimated_value",
                    "probability",
                    "expected_close_date",
                )
            },
        ),
        (
            "Assignment (RBAC)",
            {
                "fields": (
                    "owner",
                    "manager",
                    "assigned_at",
                )
            },
        ),
        (
            "Follow-up",
            {
                "fields": (
                    "next_follow_up",
                    "last_contacted",
                )
            },
        ),
        (
            "Additional Information",
            {
                "fields": (
                    "tags",
                    "notes",
                    "lost_reason",
                    "consent_to_contact",
                )
            },
        ),
        (
            "System Information",
            {
                "fields": (
                    "created_at",
                    "updated_at",
                )
            },
        ),
    )

    actions = (
        "mark_as_contacted",
        "mark_as_qualified",
        "mark_as_proposal_sent",
        "mark_as_won",
        "mark_as_lost",
        "mark_as_disqualified",
        "assign_to_me",
    )

    # --------------------------------------------------------
    # DISPLAY HELPERS
    # --------------------------------------------------------

    @admin.display(description="Status")
    def status_badge(self, obj):
        colors = {
            "new": "#6c757d",
            "assigned": "#17a2b8",
            "contacted": "#0d6efd",
            "in_followup": "#ffc107",
            "proposal_sent": "#fd7e14",
            "negotiation": "#6610f2",
            "won": "#198754",
            "lost": "#dc3545",
            "disqualified": "#495057",
        }
        color = colors.get(obj.stage, "#6c757d")
        status = obj.get_stage_display()
        return format_html(
            '<span style="background:{};color:white;padding:4px 9px;'
            'border-radius:12px;font-size:11px;font-weight:600;">{}</span>',
            color, status,
        )

    @admin.display(description="Temperature")
    def temperature_badge(self, obj):
        colors = {"hot": "#dc3545", "warm": "#fd7e14", "cold": "#0d6efd"}
        color = colors.get(obj.temperature, "#6c757d")
        temp = obj.get_temperature_display()
        return format_html(
            '<span style="color:{};font-weight:700;">{}</span>', color, temp,
        )

    @admin.display(description="Priority")
    def priority_badge(self, obj):
        colors = {"high": "#dc3545", "urgent": "#6610f2", "medium": "#fd7e14", "low": "#198754"}
        color = colors.get(obj.priority, "#6c757d")
        pri = obj.get_priority_display()
        return format_html(
            '<span style="color:{};font-weight:600;">{}</span>', color, pri,
        )

    @admin.display(description="Deal Value")
    def deal_value_display(self, obj):
        if obj.estimated_value == 0:
            return "-"
        return f"₹{obj.estimated_value:,.2f}"

    @admin.display(description="Services")
    def services_list(self, obj):
        svcs = obj.services.all()
        if not svcs:
            return "-"
        return format_html(
            ", ".join(s.name for s in svcs),
        )

    # --------------------------------------------------------
    # RBAC — filter queryset based on user role
    # --------------------------------------------------------

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        qs = qs.select_related("source", "owner", "manager")
        qs = qs.prefetch_related("services")

        if request.user.is_superuser:
            return qs

        profile = getattr(request.user, "profile", None)
        if profile is None:
            return qs.none()

        role = profile.role.name if profile.role else None

        if role == "director":
            return qs
        if role == "bds_manager":
            return qs.filter(manager=request.user)
        if role == "bds_exec":
            return qs.filter(owner=request.user)
        if role == "delivery_lead":
            return qs.filter(handovers__department__head=request.user)
        return qs.none()

    def get_fieldsets(self, request, obj=None):
        fieldsets = super().get_fieldsets(request, obj)

        profile = getattr(request.user, "profile", None)
        role = profile.role.name if profile and profile.role else None

        if request.user.is_superuser or role == "director":
            return fieldsets

        if role == "bds_manager":
            return fieldsets

        if role in ("bds_exec", "delivery_lead"):
            return fieldsets

        return fieldsets

    # --------------------------------------------------------
    # ACTIONS
    # --------------------------------------------------------

    @admin.action(description="Mark selected leads as Contacted")
    def mark_as_contacted(self, request, queryset):
        updated = queryset.update(stage="contacted")
        self.message_user(request, f"{updated} lead(s) marked as Contacted.")

    @admin.action(description="Mark selected leads as Proposal Sent")
    def mark_as_proposal_sent(self, request, queryset):
        updated = queryset.update(stage="proposal_sent")
        self.message_user(request, f"{updated} lead(s) marked as Proposal Sent.")

    @admin.action(description="Mark selected leads as Qualified")
    def mark_as_qualified(self, request, queryset):
        updated = queryset.update(stage="in_followup")
        self.message_user(request, f"{updated} lead(s) moved to In Follow-up.")

    @admin.action(description="Mark selected leads as Won")
    def mark_as_won(self, request, queryset):
        updated = queryset.update(stage="won", probability=100)
        self.message_user(request, f"{updated} lead(s) marked as Won.")

    @admin.action(description="Mark selected leads as Lost")
    def mark_as_lost(self, request, queryset):
        updated = queryset.update(stage="lost", probability=0)
        self.message_user(request, f"{updated} lead(s) marked as Lost.")

    @admin.action(description="Mark selected leads as Disqualified")
    def mark_as_disqualified(self, request, queryset):
        updated = queryset.update(stage="disqualified")
        self.message_user(request, f"{updated} lead(s) marked as Disqualified.")

    @admin.action(description="Assign selected leads to me")
    def assign_to_me(self, request, queryset):
        updated = queryset.update(owner=request.user, manager=request.user, assigned_at=timezone.now())
        self.message_user(request, f"{updated} lead(s) assigned to you.")


# ============================================================
# ACTIVITY ADMIN
# ============================================================

@admin.register(Activity)
class ActivityAdmin(admin.ModelAdmin):
    list_display = ("lead", "activity_type", "outcome", "subject", "completed", "created_by", "created_at")
    list_filter = ("activity_type", "outcome", "completed", "created_at", "created_by")
    search_fields = ("lead__name", "lead__company", "subject", "body")
    autocomplete_fields = ("lead", "created_by")
    readonly_fields = ("created_at", "updated_at")
    date_hierarchy = "created_at"
    list_per_page = 50

    fieldsets = (
        (None, {
            "fields": ("lead", "activity_type", "outcome", "subject", "body", "due_at", "completed", "created_by")
        }),
        ("System", {"fields": ("created_at", "updated_at"), "classes": ("collapse",)}),
    )


# ============================================================
# FOLLOW-UP SCHEDULE ADMIN
# ============================================================

@admin.register(FollowUpSchedule)
class FollowUpScheduleAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "lead",
        "due_at",
        "status",
        "snooze_until",
        "notification_sent",
        "assigned_to",
        "is_overdue",
    )
    list_filter = (
        "status",
        "notification_sent",
        "due_at",
        "assigned_to",
        "created_by",
    )
    search_fields = ("title", "description", "lead__name", "lead__company")
    autocomplete_fields = ("lead", "assigned_to", "created_by")
    date_hierarchy = "due_at"
    list_per_page = 50

    fieldsets = (
        (None, {
            "fields": (
                "lead", "title", "description", "due_at",
                "status", "snooze_until", "notification_sent",
                "assigned_to", "created_by",
            )
        }),
    )

    @admin.display(boolean=True, description="Overdue?")
    def is_overdue(self, obj):
        return obj.status == "pending" and obj.due_at < timezone.now()

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.select_related("lead", "assigned_to", "created_by")


# ============================================================
# TASK ADMIN
# ============================================================

@admin.register(Task)
class TaskAdmin(admin.ModelAdmin):
    list_display = ("title", "lead", "assigned_to", "due_at", "status", "created_at")
    list_filter = ("status", "due_at", "assigned_to", "created_at")
    search_fields = ("title", "description", "lead__name", "lead__company")
    autocomplete_fields = ("lead", "assigned_to")
    readonly_fields = ("created_at", "updated_at")
    ordering = ("status", "due_at", "-created_at")
    list_per_page = 50

    fieldsets = (
        (None, {
            "fields": ("title", "description", "lead", "assigned_to", "due_at", "status")
        }),
        ("System", {"fields": ("created_at", "updated_at"), "classes": ("collapse",)}),
    )


# ============================================================
# LEAD STATUS HISTORY ADMIN
# ============================================================

@admin.register(LeadStatusHistory)
class LeadStatusHistoryAdmin(admin.ModelAdmin):
    list_display = ("lead", "from_stage", "to_stage", "changed_by", "changed_at")
    list_filter = ("from_stage", "to_stage", "changed_by", "changed_at")
    search_fields = ("lead__name", "lead__company", "reason")
    autocomplete_fields = ("lead", "changed_by")
    readonly_fields = (
        "lead", "from_stage", "to_stage", "changed_by", "changed_at", "reason",
    )
    date_hierarchy = "changed_at"
    list_per_page = 50

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


# ============================================================
# LOST REASON LOG ADMIN
# ============================================================

@admin.register(LostReasonLog)
class LostReasonLogAdmin(admin.ModelAdmin):
    list_display = ("lead", "reason", "notes_preview", "logged_by", "logged_at")
    list_filter = ("reason", "logged_at", "logged_by")
    search_fields = ("lead__name", "lead__company", "notes")
    autocomplete_fields = ("lead", "logged_by")
    readonly_fields = ("lead", "reason", "notes", "logged_by", "logged_at")
    date_hierarchy = "logged_at"
    list_per_page = 50

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    @admin.display(description="Notes")
    def notes_preview(self, obj):
        return (obj.notes[:60] + "...") if len(obj.notes) > 60 else obj.notes


# ============================================================
# SERVICE HANDOVER ADMIN
# ============================================================

@admin.register(ServiceHandover)
class ServiceHandoverAdmin(admin.ModelAdmin):
    list_display = (
        "lead", "service", "department", "status",
        "target_delivery_date", "approved_quote", "accepted_at",
    )
    list_filter = ("status", "department", "service", "target_delivery_date")
    search_fields = ("lead__name", "lead__company", "service__name", "department__name")
    autocomplete_fields = ("lead", "service", "department", "accepted_by")
    readonly_fields = ("accepted_at",)
    list_per_page = 50

    fieldsets = (
        (None, {
            "fields": (
                "lead", "service", "department",
                "target_deliverable", "target_delivery_date",
                "approved_quote", "billing_type",
            )
        }),
        ("Scoping", {
            "fields": ("scope_notes", "handover_notes"),
            "classes": ("collapse",),
        }),
        ("Acceptance", {
            "fields": ("status", "accepted_by", "accepted_at"),
        }),
    )


# ============================================================
# DEAL ADMIN
# ============================================================

@admin.register(Deal)
class DealAdmin(admin.ModelAdmin):
    list_display = (
        "id", "lead", "value", "service", "expected_close",
        "renewal_date", "status",
    )
    list_filter = ("status", "expected_close", "renewal_date")
    search_fields = ("lead__name", "lead__company")
    autocomplete_fields = ("lead", "service")
    readonly_fields = ("created_at", "updated_at")
    list_per_page = 50

    fieldsets = (
        (None, {
            "fields": (
                "lead", "value", "service", "expected_close",
                "contract_start", "renewal_date", "renewal_reminder_days",
                "status", "proposal_url", "notes",
            )
        }),
        ("System", {"fields": ("created_at", "updated_at"), "classes": ("collapse",)}),
    )


# ============================================================
# LEAD NOTE ADMIN
# ============================================================

@admin.register(LeadNote)
class LeadNoteAdmin(admin.ModelAdmin):
    list_display = ("lead", "body_preview", "created_by", "created_at")
    search_fields = ("lead__name", "lead__company", "body")
    autocomplete_fields = ("lead", "created_by")
    readonly_fields = ("created_at", "updated_at")
    list_per_page = 50

    @admin.display(description="Body")
    def body_preview(self, obj):
        return (obj.body[:80] + "...") if len(obj.body) > 80 else obj.body


# ============================================================
# MEETING ADMIN
# ============================================================

@admin.register(Meeting)
class MeetingAdmin(admin.ModelAdmin):
    list_display = ("title", "lead", "meeting_type", "scheduled_at", "status", "duration_minutes")
    list_filter = ("status", "meeting_type", "scheduled_at")
    search_fields = ("title", "lead__name", "lead__company", "description")
    autocomplete_fields = ("lead", "created_by")
    filter_horizontal = ("participants",)
    date_hierarchy = "scheduled_at"
    list_per_page = 50

    fieldsets = (
        (None, {
            "fields": (
                "lead", "title", "description",
                "meeting_type", "scheduled_at", "duration_minutes",
                "location", "status", "participants",
            )
        }),
        ("System", {"fields": ("created_at", "updated_at"), "classes": ("collapse",)}),
    )


# ============================================================
# REMINDER ADMIN
# ============================================================

@admin.register(Reminder)
class ReminderAdmin(admin.ModelAdmin):
    list_display = (
        "title", "reminder_type", "due_at", "status",
        "notification_sent", "assigned_to", "is_overdue",
    )
    list_filter = ("reminder_type", "status", "notification_sent", "due_at")
    search_fields = ("title", "description", "related_lead__name", "related_lead__company")
    autocomplete_fields = ("related_lead", "related_meeting", "assigned_to", "created_by")
    date_hierarchy = "due_at"
    list_per_page = 50

    @admin.display(boolean=True, description="Overdue?")
    def is_overdue(self, obj):
        return obj.status in ("pending", "sent") and obj.due_at < timezone.now()

    fieldsets = (
        (None, {
            "fields": (
                "title", "description", "reminder_type", "due_at",
                "snooze_until", "status", "notification_sent",
                "assigned_to", "created_by",
            )
        }),
        ("Related", {
            "fields": ("related_lead", "related_meeting"),
            "classes": ("collapse",),
        }),
    )


# ============================================================
# PROPOSAL / QUOTATION ADMIN
# ============================================================

@admin.register(Proposal)
class ProposalAdmin(admin.ModelAdmin):
    list_display = (
        "title", "lead", "billing_type", "subtotal", "total_value",
        "tax_rate", "status", "valid_until", "created_at",
    )
    list_filter = ("status", "billing_type", "valid_until")
    search_fields = ("title", "lead__name", "lead__company", "scope")
    autocomplete_fields = ("lead", "services")
    filter_horizontal = ("services",)
    date_hierarchy = "created_at"
    list_per_page = 50

    fieldsets = (
        (None, {
            "fields": (
                "lead", "title", "services",
                "billing_type", "subtotal", "tax_rate", "total_value",
                "status", "valid_until",
            )
        }),
        ("Content", {"fields": ("terms", "scope", "file")}),
    )


# ============================================================
# USER PROFILE & ROLE ADMIN (Control app integration)
# ============================================================

from django.contrib.auth.models import Group  # noqa: E402


admin.site.unregister(User)


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ("username", "email", "first_name", "last_name", "role_display", "is_staff")
    list_filter = ("is_staff", "is_superuser", "groups")

    def role_display(self, obj):
        profile = getattr(obj, "profile", None)
        if profile and profile.role:
            return profile.role.label
        return "-"

    role_display.short_description = "Role"
    role_display.admin_order_field = "profile__role__label"


# Unregister Group (we use Role + UserProfile instead)
admin.site.unregister(Group)
