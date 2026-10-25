from django.contrib import admin

from .models import AttendanceAttempt, AttendanceRecord, FaceTemplate, OfficeLocation


@admin.register(OfficeLocation)
class OfficeLocationAdmin(admin.ModelAdmin):
    list_display = ("name", "latitude", "longitude", "radius_m", "is_active")


@admin.register(AttendanceRecord)
class AttendanceRecordAdmin(admin.ModelAdmin):
    list_display = ("employee", "date", "status", "check_in", "check_out", "in_within_geofence")
    list_filter = ("status", "date")
    search_fields = ("employee__employee_code", "employee__user__username")
    exclude = ("in_snapshot", "out_snapshot")


@admin.register(AttendanceAttempt)
class AttendanceAttemptAdmin(admin.ModelAdmin):
    list_display = ("employee", "kind", "success", "reason", "face_score", "created_at")
    list_filter = ("kind", "success")


@admin.register(FaceTemplate)
class FaceTemplateAdmin(admin.ModelAdmin):
    list_display = ("employee", "created_at")
    exclude = ("embedding", "snapshot")
