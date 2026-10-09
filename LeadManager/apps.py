from django.apps import AppConfig


class LeadManagerConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "LeadManager"
    verbose_name = "LeadPlus-360"

    def ready(self):
        import LeadManager.signals
