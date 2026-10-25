from django.urls import path

from . import tv_views

urlpatterns = [
    path("<str:token>/", tv_views.tv_page, name="tv_page"),
    path("<str:token>/data/", tv_views.tv_data, name="tv_data"),
]
