from django.urls import path

from . import views

urlpatterns = [
    path("", views.dashboard, name="outreach_dashboard"),
    path("prospects/", views.prospect_list, name="outreach_prospects"),
    path("prospects/contacted/", views.contacted_prospects, name="outreach_contacted"),
    path("prospects/new/", views.prospect_new, name="outreach_prospect_new"),
    path("prospects/export/", views.prospect_export, name="outreach_export"),
    path("templates/", views.pitch_templates, name="outreach_templates"),
    path("templates/<int:pk>/", views.pitch_templates, name="outreach_template_edit"),
    path("prospects/<int:pk>/", views.prospect_detail, name="outreach_prospect_detail"),
    path("import/", views.import_leads, name="outreach_import"),
    path("cohorts/", views.cohorts, name="outreach_cohorts"),
    path("campaigns/", views.campaigns, name="outreach_campaigns"),
    path("campaigns/new/", views.campaign_new, name="outreach_campaign_new"),
    path("campaigns/<int:pk>/", views.campaign_detail, name="outreach_campaign_detail"),
    path("approval/", views.outbox, name="outreach_outbox"),
    path("settings/", views.settings_view, name="outreach_settings"),
    path("u/<str:token>/", views.unsubscribe, name="outreach_unsubscribe"),
]
