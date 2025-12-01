from django.apps import AppConfig


class ATasksConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'a_tasks'

    def ready(self):
        """Import signals when the app is ready"""
        import a_tasks.signals  # noqa
