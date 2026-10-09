from django.contrib import admin
from django.contrib import messages as admin_messages
from django.utils import timezone

from .models import (
    Employee, EmployeeDocument, OnboardingTask, OnboardingTemplate, OnboardingTemplateTask,
)


class TemplateTaskInline(admin.TabularInline):
    model = OnboardingTemplateTask
    extra = 1


@admin.register(OnboardingTemplate)
class OnboardingTemplateAdmin(admin.ModelAdmin):
    list_display = ("name", "department", "is_default", "is_active")
    inlines = [TemplateTaskInline]


@admin.register(Employee)
class EmployeeAdmin(admin.ModelAdmin):
    list_display = ("employee_code", "user", "department", "designation", "status", "work_mode")
    list_filter = ("status", "department", "work_mode", "employment_type")
    search_fields = ("employee_code", "user__username", "user__first_name", "user__last_name")
    raw_id_fields = ("user", "manager")


@admin.register(OnboardingTask)
class OnboardingTaskAdmin(admin.ModelAdmin):
    list_display = ("employee", "title", "status", "responsible", "submission_count", "employee_locked", "completed_at")
    list_filter = ("status", "responsible", "submission_count", "category")
    search_fields = ("employee__employee_code", "employee__user__username", "title")
    readonly_fields = ("employee", "employee_locked")
    raw_id_fields = ("employee",)

    @admin.display(boolean=True, description="Locked")
    def employee_locked(self, obj):
        return obj.employee_locked

    @admin.action(description="Reset employee submission count (allow one more employee submission)")
    def reset_employee_limit(self, request, queryset):
        count = 0
        for task in queryset:
            task.submission_count = 0
            task.save(update_fields=["submission_count"])
            count += 1
        self.message_user(request, f"{count} task(s) reset for employee submission.", level=admin_messages.INFO)

    actions = ["reset_employee_limit"]


admin.site.register(EmployeeDocument)
