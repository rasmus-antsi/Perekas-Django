"""
Maintenance functions for daily tasks.
"""
import logging
from django.utils import timezone
from datetime import timedelta
from a_tasks.models import Task, TaskRecurrence
from a_tasks.recurrence_utils import calculate_next_occurrence

logger = logging.getLogger(__name__)


def reset_assigned_to_for_all_tasks():
    """
    Resets assigned_to to None for all incomplete tasks.
    This ensures children can't "lock" tasks for multiple days.
    Returns the number of tasks updated.
    """
    incomplete_tasks = Task.objects.filter(
        completed=False,
        assigned_to__isnull=False
    )
    
    count = incomplete_tasks.count()
    
    if count > 0:
        incomplete_tasks.update(assigned_to=None)
        logger.info(f"Reset assigned_to for {count} incomplete task(s)")
        return count
    
    logger.info("No incomplete tasks to reset assigned_to")
    return 0


def create_recurring_tasks_for_today(today):
    """
    Creates recurring tasks that should occur today.
    If next_occurrence is in the past, creates task for today or updates due_date.
    If a new task is created for today and there's an old uncompleted task for the same recurrence,
    the old task is deleted.
    Returns the number of tasks created/updated.
    """
    created_count = 0
    updated_count = 0
    
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
        
        # Calculate the due date for the new task
        new_due_date = recurrence.next_occurrence.date()
        
        # If next_occurrence is in the past, we need to create/update task for today
        if new_due_date < today:
            # Find existing uncompleted task for this recurrence (same name, same family)
            existing_task = Task.objects.filter(
                family=recurrence.task.family,
                name=recurrence.task.name,
                completed=False
            ).exclude(id=recurrence.task.id).order_by('-due_date').first()
            
            if existing_task:
                # Update due_date to today if task exists but is in the past
                if existing_task.due_date < today:
                    existing_task.due_date = today
                    existing_task.assigned_to = None  # Reset assignment
                    existing_task.completed = False
                    existing_task.completed_by = None
                    existing_task.completed_at = None
                    existing_task.approved = False
                    existing_task.approved_by = None
                    existing_task.approved_at = None
                    existing_task.started_at = None
                    existing_task.save()
                    updated_count += 1
                    logger.info(
                        f"Updated due_date to {today} for existing task '{existing_task.name}' (ID: {existing_task.id})"
                    )
                # Even if due_date is today, we still need to update next_occurrence
            else:
                # Create new task for today
                new_task = Task.objects.create(
                    name=recurrence.task.name,
                    description=recurrence.task.description,
                    family=recurrence.task.family,
                    assigned_to=None,  # Don't copy assigned_to, let it be None
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
                logger.info(
                    f"Created recurring task '{new_task.name}' (ID: {new_task.id}) "
                    f"for {today} (was due {new_due_date})"
                )
            
            # Calculate next occurrence from today (always update if next_occurrence was in the past)
            next_due_date, next_occurrence = calculate_next_occurrence(
                today, recurrence.frequency, recurrence.interval,
                day_of_week=recurrence.day_of_week,
                day_of_month=recurrence.day_of_month
            )
            recurrence.next_occurrence = next_occurrence
            recurrence.save()
            continue
        
        # If it's due today
        if new_due_date == today:
            # Check if a task for today already exists for this recurrence
            existing_task_today = Task.objects.filter(
                family=recurrence.task.family,
                name=recurrence.task.name,
                due_date=today,
                completed=False
            ).exclude(id=recurrence.task.id).first()
            
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
                assigned_to=None,  # Don't copy assigned_to, let it be None
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
    
    return created_count + updated_count


def delete_completed_tasks():
    """
    Deletes tasks that have been both completed and approved by a parent.
    Returns the number of tasks deleted.
    """
    completed_and_approved_tasks = Task.objects.filter(
        completed=True,
        completed_at__isnull=False,
        approved=True
    )
    
    count = completed_and_approved_tasks.count()
    
    if count > 0:
        deleted_count, _ = completed_and_approved_tasks.delete()
        logger.info(f"Deleted {deleted_count} completed and approved task(s)")
        return deleted_count
    
    logger.info("No completed and approved tasks to delete")
    return 0


def clear_shopping_cart():
    """
    Deletes all items in the shopping cart (in_cart=True).
    Returns the number of items deleted.
    """
    try:
        from a_shopping.models import ShoppingListItem
        
        cart_items = ShoppingListItem.objects.filter(in_cart=True)
        
        count = cart_items.count()
        
        if count > 0:
            deleted_count, _ = cart_items.delete()
            logger.info(f"Deleted {deleted_count} item(s) from shopping cart")
            return deleted_count
        
        logger.info("No items in shopping cart to delete")
        return 0
    except Exception as e:
        logger.error(f"Error clearing shopping cart: {e}")
        return 0
