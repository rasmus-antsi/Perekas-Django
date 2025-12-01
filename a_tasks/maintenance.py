"""
Maintenance tasks that run when users log in.
These tasks ensure recurring tasks are created and old tasks are cleaned up.
"""
import logging
from django.utils import timezone
from datetime import timedelta

try:
    from django.core.cache import cache
    CACHE_AVAILABLE = True
except Exception:
    CACHE_AVAILABLE = False
    cache = None

from .models import Task, TaskRecurrence

logger = logging.getLogger(__name__)


def create_recurring_tasks():
    """
    Creates new task instances for recurring tasks that are due.
    Returns the number of tasks created.
    """
    now = timezone.now()
    today = now.date()
    
    # Find all recurrences where next_occurrence is due (today or earlier)
    due_recurrences = TaskRecurrence.objects.filter(
        next_occurrence__lte=now
    ).select_related('task', 'task__family', 'task__assigned_to', 'task__created_by')
    
    created_count = 0
    
    for recurrence in due_recurrences:
        # Check if end_date has passed
        if recurrence.end_date and recurrence.end_date < today:
            # Delete the recurrence as it's expired
            recurrence.delete()
            logger.info(
                f"Deleted expired recurrence for task '{recurrence.task.name}' "
                f"(ID: {recurrence.task.id}) - end date {recurrence.end_date} passed"
            )
            continue
        
        # Check if a task with this name and due date already exists for this family
        # (to avoid duplicates)
        new_due_date = recurrence.next_occurrence.date()
        existing_task = Task.objects.filter(
            family=recurrence.task.family,
            name=recurrence.task.name,
            due_date=new_due_date,
            completed=False
        ).first()
        
        if existing_task:
            # Task already exists, just update the recurrence
            if recurrence.frequency == TaskRecurrence.FREQUENCY_DAILY:
                recurrence.next_occurrence = now + timedelta(days=1)
            elif recurrence.frequency == TaskRecurrence.FREQUENCY_WEEKLY:
                recurrence.next_occurrence = now + timedelta(days=7)
            elif recurrence.frequency == TaskRecurrence.FREQUENCY_MONTHLY:
                recurrence.next_occurrence = now + timedelta(days=30)
            recurrence.save()
            continue
        
        # Create new task instance
        new_task = Task.objects.create(
            name=recurrence.task.name,
            description=recurrence.task.description,
            family=recurrence.task.family,
            assigned_to=recurrence.task.assigned_to,
            created_by=recurrence.task.created_by,
            due_date=new_due_date,
            priority=recurrence.task.priority,
            points=recurrence.task.points,
            completed=False,
            completed_by=None,
            completed_at=None,
            approved=False,
            approved_by=None,
            approved_at=None,
            started_at=None,
        )
        created_count += 1
        
        # Update recurrence next_occurrence
        if recurrence.frequency == TaskRecurrence.FREQUENCY_DAILY:
            recurrence.next_occurrence = now + timedelta(days=1)
        elif recurrence.frequency == TaskRecurrence.FREQUENCY_WEEKLY:
            recurrence.next_occurrence = now + timedelta(days=7)
        elif recurrence.frequency == TaskRecurrence.FREQUENCY_MONTHLY:
            recurrence.next_occurrence = now + timedelta(days=30)
        
        # Create a new recurrence for the new task
        TaskRecurrence.objects.create(
            task=new_task,
            frequency=recurrence.frequency,
            interval=recurrence.interval,
            end_date=recurrence.end_date,
            next_occurrence=recurrence.next_occurrence,
        )
        
        # Delete the old recurrence (it's been replaced by the new one)
        recurrence.delete()
        
        logger.info(
            f"Created recurring task '{new_task.name}' (ID: {new_task.id}) "
            f"from original task ID {recurrence.task.id} with due date {new_due_date}"
        )
    
    return created_count


def delete_old_completed_tasks():
    """
    Deletes tasks that were completed more than 48 hours ago.
    Returns the number of tasks deleted.
    """
    cutoff_time = timezone.now() - timedelta(hours=48)
    
    old_completed_tasks = Task.objects.filter(
        completed=True,
        completed_at__isnull=False,
        completed_at__lt=cutoff_time
    )
    
    deleted_count, _ = old_completed_tasks.delete()
    
    if deleted_count > 0:
        logger.info(f"Auto-deleted {deleted_count} task(s) that were completed 48+ hours ago.")
    
    return deleted_count


def run_maintenance_tasks():
    """
    Runs all maintenance tasks.
    Uses cache (if available) to ensure it only runs once per day globally.
    Falls back to running every time if cache is not configured.
    Returns dict with results.
    """
    # Try to use cache to ensure maintenance only runs once per day globally
    today = timezone.now().date().isoformat()
    
    if CACHE_AVAILABLE and cache:
        try:
            cache_key = 'maintenance_tasks_last_run'
            last_run = cache.get(cache_key)
            if last_run == today:
                # Already ran today, skip
                return {
                    'skipped': True,
                    'message': 'Maintenance tasks already ran today'
                }
        except Exception:
            # Cache error - continue anyway
            pass
    
    try:
        # Run maintenance tasks
        recurring_created = create_recurring_tasks()
        old_tasks_deleted = delete_old_completed_tasks()
        
        # Mark as run today (if cache is available)
        if CACHE_AVAILABLE and cache:
            try:
                cache_key = 'maintenance_tasks_last_run'
                cache.set(cache_key, today, timeout=86400)  # 24 hours
            except Exception:
                # Cache error - that's okay, we'll rely on session flag
                pass
        
        result = {
            'skipped': False,
            'recurring_tasks_created': recurring_created,
            'old_tasks_deleted': old_tasks_deleted,
            'message': f'Created {recurring_created} recurring task(s), deleted {old_tasks_deleted} old task(s)'
        }
        
        logger.info(f"Maintenance tasks completed: {result['message']}")
        return result
        
    except Exception as e:
        logger.error(f"Error running maintenance tasks: {e}", exc_info=True)
        return {
            'skipped': False,
            'error': str(e),
            'message': f'Error running maintenance tasks: {e}'
        }

