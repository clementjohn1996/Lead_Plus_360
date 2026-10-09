from django.contrib import admin

from .models import (
    Appraisal,
    BDEConfig,
    BDETarget,
    ImprovementPlan,
    ImprovementUpdate,
    KPI,
    KPIEntry,
    MonthlyPerformance,
    PerformanceAlert,
    PerformanceAudit,
    TVDisplay, TVPoster,
)


@admin.register(KPI)
class KPIAdmin(admin.ModelAdmin):
    list_display = ("name", "department", "auto_key", "weight", "default_target", "is_active")
    list_filter = ("department", "is_active")
    search_fields = ("name", "description")


@admin.register(KPIEntry)
class KPIEntryAdmin(admin.ModelAdmin):
    list_display = ("employee", "kpi", "month", "target", "actual")
    list_filter = ("month", "kpi")
    search_fields = ("employee__user__first_name", "employee__user__last_name", "employee__employee_code")


@admin.register(TVDisplay)
class TVDisplayAdmin(admin.ModelAdmin):
    list_display = ("name", "department", "seconds_per_slide", "is_active")
    readonly_fields = ("token",)


@admin.register(BDEConfig)
class BDEConfigAdmin(admin.ModelAdmin):
    list_display = ("default_target", "slabs", "red_max", "yellow_max", "red_pip_months", "yellow_pip_months", "window_months")

    def has_add_permission(self, request):
        return not BDEConfig.objects.exists() and super().has_add_permission(request)


@admin.register(BDETarget)
class BDETargetAdmin(admin.ModelAdmin):
    list_display = ("employee", "monthly_target", "updated_at")
    search_fields = ("employee__user__first_name", "employee__user__last_name", "employee__employee_code")


@admin.register(MonthlyPerformance)
class MonthlyPerformanceAdmin(admin.ModelAdmin):
    list_display = ("employee", "month", "target", "revenue", "achievement_pct", "slab", "effective_colour", "status", "is_closed")
    list_filter = ("colour", "status", "is_closed", "month")
    search_fields = ("employee__user__first_name", "employee__user__last_name", "employee__employee_code")
    readonly_fields = ("updated_at",)

    @admin.display(description="Colour")
    def effective_colour(self, obj):
        return obj.effective_colour


@admin.register(ImprovementPlan)
class ImprovementPlanAdmin(admin.ModelAdmin):
    list_display = ("employee", "trigger_reason", "start_date", "review_date", "status", "auto_created")
    list_filter = ("status", "auto_created")
    search_fields = ("employee__user__first_name", "employee__user__last_name", "employee__employee_code", "trigger_reason")


@admin.register(ImprovementUpdate)
class ImprovementUpdateAdmin(admin.ModelAdmin):
    list_display = ("plan", "date", "score", "author")
    list_filter = ("date",)
    search_fields = ("plan__employee__user__first_name", "plan__employee__user__last_name", "note")


@admin.register(Appraisal)
class AppraisalAdmin(admin.ModelAdmin):
    list_display = ("employee", "period_start", "period_end", "avg_achievement", "green_months", "yellow_months", "red_months", "decision", "review_date")
    list_filter = ("decision", "period_end")
    search_fields = ("employee__user__first_name", "employee__user__last_name", "employee__employee_code")


@admin.register(PerformanceAlert)
class PerformanceAlertAdmin(admin.ModelAdmin):
    list_display = ("employee", "kind", "month", "is_read", "created_at")
    list_filter = ("kind", "is_read", "month")
    search_fields = ("employee__user__first_name", "employee__user__last_name", "message")


@admin.register(PerformanceAudit)
class PerformanceAuditAdmin(admin.ModelAdmin):
    list_display = ("created_at", "user", "employee", "action", "old_value", "new_value")
    list_filter = ("action", "created_at")
    search_fields = ("action", "old_value", "new_value", "employee__user__username")
    readonly_fields = ("user", "employee", "action", "old_value", "new_value", "created_at")


@admin.register(TVPoster)
class TVPosterAdmin(admin.ModelAdmin):
    list_display = ("title", "seconds", "sort_order", "is_active", "created_at")
    list_filter = ("is_active",)
    search_fields = ("title", "subtitle")
    ordering = ("sort_order", "-created_at")
