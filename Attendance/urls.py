from django.urls import path

from . import views

urlpatterns = [
    path("", views.punch_page, name="attendance"),
    path("api/enroll/", views.api_enroll, name="attendance_api_enroll"),
    path("api/punch/", views.api_punch, name="attendance_api_punch"),
    path("snapshot/<int:record_id>/<str:which>/", views.snapshot, name="attendance_snapshot"),
    path("manage/", views.hr_dashboard, name="attendance_dashboard"),
    path("manage/monthly/", views.monthly_report, name="attendance_monthly"),
    path("manage/offices/", views.offices, name="attendance_offices"),
    path("manage/offices/<int:pk>/", views.offices, name="attendance_office_edit"),
    path("manage/offices/<int:pk>/delete/", views.office_delete, name="attendance_office_delete"),
    path("manage/reset-face/<int:employee_id>/", views.reset_face, name="attendance_reset_face"),
]
