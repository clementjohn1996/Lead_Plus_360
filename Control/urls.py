from django.contrib.auth.views import LogoutView
from django.urls import path

from . import views

urlpatterns = [
    path("", views.home, name="home"),
    path("login/", views.login_view, name="login"),
    path("logout/", LogoutView.as_view(), name="logout"),
    path("profile/", views.profile, name="profile"),
    path("control/", views.control_center, name="control_center"),
    path("control/users/<int:pk>/", views.user_action, name="user_action"),
    path("guide/", views.guide, name="guide"),
    path("roles/", views.roles, name="roles"),
    path("roles/new/", views.role_edit, name="role_create"),
    path("roles/<int:pk>/", views.role_edit, name="role_edit"),
    path("roles/<int:pk>/view/", views.role_detail, name="role_detail"),
    path("roles/<int:pk>/delete/", views.role_delete, name="role_delete"),
    path("branding/", views.branding, name="branding"),
]
