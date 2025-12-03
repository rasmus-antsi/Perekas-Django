"""
Maintenance functions for daily tasks.
"""
import logging
from django.utils import timezone
from datetime import timedelta
from a_tasks.models import Task, TaskRecurrence
from a_tasks.recurrence_utils import calculate_next_occurrence

logger = logging.getLogger(__name__)


def create_recurring_tasks_for_today(today):
    """
    Creates recurring tasks that should occur today.
    If a new task is created for today and there's an old uncompleted task for the same recurrence,
    the old task is deleted.
    Returns the number of tasks created.
    """
    created_count = 0
    
    # Find all recurrences where next_occurrence is today or earlier
    from datetime import datetime as dt
    today_start = timezone.make_aware(dt.combine(today, dt.min.time()))
    due_recurrences = TaskRecurrence.objects.filter(
        next_occurrence__lte=today_start + timedelta(days=1)
    ).select_related('task', 'task__family', 'task__assigned_to', 'task__created_by')
    
    for recurrence in due_recurrences:
        # Check if end_date has passed
        if recurrence.end_date and recurrence.end_date < today:
            recurrence.delete()
            logger.info(
                f"Deleted expired recurrence for task '{recurrence.task.name}' "
                f"(end date {recurrence.end_date} passed)"
            )
            continue
        
        # Calculate the due date for the new task (should be today)
        new_due_date = recurrence.next_occurrence.date()
        
        # Only create if it's due today
        if new_due_date != today:
            # Update recurrence to next occurrence if it's in the past
            if new_due_date < today:
                next_due_date, next_occurrence = calculate_next_occurrence(
                    new_due_date, recurrence.frequency, recurrence.interval,
                    day_of_week=recurrence.day_of_week,
                    day_of_month=recurrence.day_of_month
                )
                recurrence.next_occurrence = next_occurrence
                recurrence.save()
            continue
        
        # Check if a task for today already exists for this recurrence
        existing_task_today = Task.objects.filter(
            family=recurrence.task.family,
            name=recurrence.task.name,
            due_date=today,
            completed=False
        ).first()
        
        if existing_task_today:
            # Task for today already exists, just update the recurrence to next occurrence
            next_due_date, next_occurrence = calculate_next_occurrence(
                today, recurrence.frequency, recurrence.interval,
                day_of_week=recurrence.day_of_week,
                day_of_month=recurrence.day_of_month
            )
            recurrence.next_occurrence = next_occurrence
            recurrence.save()
            continue
        
        # Find old uncompleted tasks for this recurrence (same name, same family, but different due date)
        old_uncompleted_tasks = Task.objects.filter(
            family=recurrence.task.family,
            name=recurrence.task.name,
            completed=False,
            due_date__lt=today
        ).exclude(id=recurrence.task.id)
        
        # Delete old uncompleted tasks
        old_tasks_deleted = 0
        if old_uncompleted_tasks.exists():
            old_tasks_deleted, _ = old_uncompleted_tasks.delete()
            logger.info(
                f"Deleted {old_tasks_deleted} old uncompleted task(s) for '{recurrence.task.name}' "
                f"before creating new one for {today}"
            )
        
        # Create new task instance for today
        new_task = Task.objects.create(
            name=recurrence.task.name,
            description=recurrence.task.description,
            family=recurrence.task.family,
            assigned_to=recurrence.task.assigned_to,
            created_by=recurrence.task.created_by,
            due_date=today,
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
        
        # Calculate next occurrence
        next_due_date, next_occurrence = calculate_next_occurrence(
            today, recurrence.frequency, recurrence.interval,
            day_of_week=recurrence.day_of_week,
            day_of_month=recurrence.day_of_month
        )
        
        # Update recurrence to point to new task and set next occurrence
        recurrence.task = new_task
        recurrence.next_occurrence = next_occurrence
        recurrence.save()
        
        logger.info(
            f"Created recurring task '{new_task.name}' (ID: {new_task.id}) "
            f"for {today}, deleted {old_tasks_deleted} old task(s)"
        )
    
    return created_count


def delete_completed_tasks():
    """
    Deletes all completed tasks (daily cleanup, not 48 hours).
    Returns the number of tasks deleted.
    """
    completed_tasks = Task.objects.filter(
        completed=True,
        completed_at__isnull=False
    )
    
    count = completed_tasks.count()
    
    if count > 0:
        deleted_count, _ = completed_tasks.delete()
        logger.info(f"Deleted {deleted_count} completed task(s)")
        return deleted_count
    
    logger.info("No completed tasks to delete")
    return 0
