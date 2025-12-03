import sys
import logging
from django.apps import AppConfig

logger = logging.getLogger(__name__)


class ATasksConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'a_tasks'

    def ready(self):
        """Import signals and start scheduler when the app is ready"""
        import a_tasks.signals  # noqa
        
        # Only start scheduler in web server processes, not during migrations, tests, or in worker processes
        # Check if we're in a management command (migrate, test, collectstatic, etc.)
        is_management_command = any(
            'manage.py' in arg or 'migrate' in arg or 'test' in arg or 'collectstatic' in arg
            for arg in sys.argv if isinstance(arg, str)
        )
        
        # Check if we're running under gunicorn (production)
        is_gunicorn = 'gunicorn' in ' '.join(sys.argv) if sys.argv else False
        
        # Only start scheduler if:
        # 1. Not a management command (migrate, test, etc.)
        # 2. Running under gunicorn (production) OR running the dev server
        # Note: With gunicorn, each worker will start its own scheduler, but APScheduler handles this
        # and only one will actually run the jobs (they coordinate)
        if not is_management_command and (is_gunicorn or 'runserver' in ' '.join(sys.argv)):
            try:
                from a_tasks.scheduler import start_scheduler
                start_scheduler()
                logger.info("Task scheduler initialized and started")
            except Exception as e:
                # Don't fail app startup if scheduler fails
                logger.warning(f"Failed to start scheduler: {e}")
