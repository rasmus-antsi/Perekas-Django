"""
Main scheduler for daily maintenance tasks.
Uses APScheduler to run maintenance jobs automatically.
"""
import logging
import atexit
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from django.utils import timezone
import pytz

from a_tasks.maintenance import create_recurring_tasks_for_today, delete_completed_tasks

logger = logging.getLogger(__name__)

# Global scheduler instance
scheduler = None

# Tallinn timezone (EET/EEST - UTC+2/UTC+3)
TALLINN_TZ = pytz.timezone('Europe/Tallinn')


def start_scheduler():
    """Start the background scheduler for daily maintenance"""
    global scheduler
    
    if scheduler and scheduler.running:
        logger.info("Scheduler is already running")
        return
    
    scheduler = BackgroundScheduler()
    
    # Schedule daily maintenance at 00:00 Tallinn time every day
    scheduler.add_job(
        run_daily_maintenance,
        trigger=CronTrigger(hour=0, minute=0, timezone=TALLINN_TZ),
        id='daily_maintenance',
        name='Daily Maintenance - Create recurring tasks and cleanup',
        replace_existing=True
    )
    
    scheduler.start()
    logger.info("Daily maintenance scheduler started - will run at 00:00 Tallinn time every day")
    
    # Register shutdown handler
    atexit.register(lambda: shutdown_scheduler())


def run_daily_maintenance():
    """Run the daily maintenance tasks"""
    try:
        today = timezone.now().date()
        logger.info(f"Starting scheduled daily maintenance at {timezone.now()} (Tallinn time)")
        logger.info("=" * 60)
        
        # 1. Create recurring tasks for today
        created_count = create_recurring_tasks_for_today(today)
        logger.info(f"Created {created_count} recurring task(s) for {today}")
        
        # 2. Delete all completed tasks
        deleted_count = delete_completed_tasks()
        logger.info(f"Deleted {deleted_count} completed task(s)")
        
        logger.info("=" * 60)
        logger.info(f"Daily maintenance completed successfully at {timezone.now()}")
    except Exception as e:
        logger.error(f"Error running scheduled daily maintenance: {e}", exc_info=True)


def shutdown_scheduler():
    """Shutdown the scheduler gracefully"""
    global scheduler
    if scheduler and scheduler.running:
        scheduler.shutdown()
        logger.info("Scheduler shut down")


def is_scheduler_running():
    """Check if scheduler is running"""
    return scheduler is not None and scheduler.running
