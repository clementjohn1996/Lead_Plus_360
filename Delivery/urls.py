from django.urls import path
from . import views, calendar_views

urlpatterns = [
    path("", views.dashboard, name="delivery_dashboard"),
    path("calendar/", calendar_views.calendar_dashboard, name="delivery_calendar"),
    path("calendar/new/<int:lead_id>/", calendar_views.plan_create, name="delivery_calendar_plan_create"),
    path("calendar/plan/<int:pk>/", calendar_views.plan_edit, name="delivery_calendar_plan_edit"),
    path("calendar/plan/<int:pk>/submit/", calendar_views.submit_plan, name="delivery_calendar_plan_submit"),
    path("calendar/plan/<int:pk>/review/", calendar_views.review_plan, name="delivery_calendar_plan_review"),
    path("calendar/plan/<int:plan_id>/task/add/", calendar_views.task_add, name="delivery_calendar_task_add"),
    path("calendar/task/<int:pk>/edit/", calendar_views.task_edit, name="delivery_calendar_task_edit"),
    path("calendar/date/<str:date_str>/", calendar_views.date_view, name="delivery_calendar_date"),
    path("calendar/date/<str:date_str>/quick-add/", calendar_views.quick_add_task, name="delivery_calendar_task_quick"),
    path("calendar/packages/", calendar_views.package_manager, name="delivery_packages"),
    path("calendar/packages/create/", calendar_views.package_create, name="delivery_package_create"),
    path("calendar/packages/<int:package_id>/task/", calendar_views.package_task_create, name="delivery_package_task_create"),
    path("work/<int:pk>/", views.detail, name="delivery_detail"),
    path("work/<int:pk>/assign-bdm/", views.assign_bdm, name="delivery_assign_bdm"),
    path("work/<int:pk>/accept-bdm/", views.accept_bdm, name="delivery_accept_bdm"),
    path("work/<int:pk>/assign-pm/", views.assign_pm, name="delivery_assign_pm"),
    path("work/<int:pk>/assign-team/", views.assign_team, name="delivery_assign_team"),
    path("assignment/<int:pk>/update/", views.update_assignment, name="delivery_update_assignment"),
    path("work/<int:pk>/complete/", views.complete_work, name="delivery_complete"),
    path("work/<int:pk>/complete/", views.complete_work, name="delivery_complete_work"),
]
