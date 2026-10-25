from django.apps import AppConfig

class ControlConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'Control'

    def ready(self):
        import Control.signals
