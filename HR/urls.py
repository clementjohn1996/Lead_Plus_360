from django.urls import path

from . import views

urlpatterns = [
    path("", views.employee_list, name="hr_employees"),
    path("departments/", views.department_list, name="hr_departments"),
    path("new/", views.employee_create, name="hr_employee_create"),
    path("onboarding/", views.onboarding_board, name="hr_onboarding"),
    path("my-onboarding/", views.my_onboarding, name="my_onboarding"),
    path("tasks/<int:task_id>/update/", views.task_update, name="hr_task_update"),
    path("workflows/", views.workflows, name="hr_workflows"),
    path("workflows/new/", views.workflow_edit, name="hr_workflow_create"),
    path("workflows/<int:pk>/", views.workflow_edit, name="hr_workflow_edit"),
    path("workflows/<int:pk>/delete/", views.workflow_delete, name="hr_workflow_delete"),
    path("<int:pk>/", views.employee_detail, name="hr_employee_detail"),
    path("<int:pk>/edit/", views.employee_edit, name="hr_employee_edit"),
    path("<int:pk>/documents/add/", views.employee_document_add, name="hr_document_add"),
    path("<int:pk>/tasks/add/", views.employee_task_add, name="hr_task_add"),
    path("<int:pk>/checklist/", views.employee_regenerate_checklist, name="hr_checklist"),
]
