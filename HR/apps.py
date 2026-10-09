from django.apps import AppConfig


class HRConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "HR"
    verbose_name = "HR"

    def ready(self):
        from . import signals  # noqa: F401
