from django.urls import path
from . import views
urlpatterns=[
 path("",views.dashboard,name="leadplus_dashboard"),
 path("leads/",views.lead_list,name="leads"),
 path("leads/new/",views.lead_create,name="lead_create"),
 path("leads/<int:lead_id>/",views.lead_detail,name="lead_detail"),
 path("leads/<int:lead_id>/edit/",views.lead_edit,name="lead_edit"),
 path("leads/<int:lead_id>/activity/",views.add_activity,name="add_activity"),
 path("pipeline/",views.pipeline,name="pipeline"),
 path("tasks/",views.tasks,name="tasks"),
 path("tasks/add/",views.add_task,name="add_task"),
 path("tasks/<int:task_id>/complete/",views.task_complete,name="task_complete"),
 path("quick-lead/",views.quick_lead,name="quick_lead"),
 path("export/leads/",views.export_leads,name="export_leads"),
]
