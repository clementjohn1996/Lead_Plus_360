from django.contrib import admin
from .models import WorkItem, WorkAssignment, WorkEvent

@admin.register(WorkItem)
class WorkItemAdmin(admin.ModelAdmin):
    list_display = ("id","title","lead","bde","bdm","project_manager","department","status","progress","due_date")
    list_filter = ("status","priority","department")
    search_fields = ("title","lead__name","lead__company")
    autocomplete_fields = ("lead","handover","service","department","bde","bdm","project_manager","created_by")

@admin.register(WorkAssignment)
class WorkAssignmentAdmin(admin.ModelAdmin):
    list_display = ("title","work","employee","role","status","progress","due_date")
    list_filter = ("status","role")
    search_fields = ("title","employee__username","employee__first_name","employee__last_name","work__title")
    autocomplete_fields = ("work","employee","assigned_by")

@admin.register(WorkEvent)
class WorkEventAdmin(admin.ModelAdmin):
    list_display = ("work","event_type","actor","from_status","to_status","created_at")
    list_filter = ("event_type","to_status")
    search_fields = ("work__title","message","actor__username")

from .calendar_models import DeliveryPackage, PackageTaskTemplate, DeliveryPlan, DeliveryCalendarTask

@admin.register(DeliveryPackage)
class DeliveryPackageAdmin(admin.ModelAdmin):
    list_display = ("name", "is_preset", "is_active", "created_by", "created_at")
    list_filter = ("is_preset", "is_active")
    search_fields = ("name", "description")

@admin.register(PackageTaskTemplate)
class PackageTaskTemplateAdmin(admin.ModelAdmin):
    list_display = ("title", "package", "task_type", "icon", "sequence", "active")
    list_filter = ("task_type", "active", "package")
    search_fields = ("title", "package__name")
    autocomplete_fields = ("package",)

@admin.register(DeliveryPlan)
class DeliveryPlanAdmin(admin.ModelAdmin):
    list_display = ("id", "lead", "package_name", "bde", "bdm", "status", "start_date", "target_completion_date", "approved_at")
    list_filter = ("status", "package")
    search_fields = ("lead__name", "lead__company", "package_name")
    autocomplete_fields = ("lead", "package", "bde", "bdm", "approved_by")

@admin.register(DeliveryCalendarTask)
class DeliveryCalendarTaskAdmin(admin.ModelAdmin):
    list_display = ("title", "plan", "task_type", "assignment_role", "assigned_to", "start_date", "due_date", "status", "progress")
    list_filter = ("task_type", "status", "assignment_role")
    search_fields = ("title", "plan__lead__name", "plan__lead__company")
    autocomplete_fields = ("plan", "template", "assigned_to")
