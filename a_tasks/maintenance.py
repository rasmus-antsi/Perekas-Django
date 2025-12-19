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
    
    Logic:
    1. Only processes recurrences where next_occurrence date is exactly today
    2. If the task referenced by recurrence is completed and approved, delete it and create a new one for today
    3. If the task is not completed and due_date doesn't match today, update due_date to today
    4. If no task exists for today, create one
    5. Always update next_occurrence to the next occurrence date
    
    The task's due_date should always match the recurrence's next_occurrence date.
    Only processes recurrences on their actual recurrence date, not every day.
    Returns the number of tasks created/updated.
    """
    created_count = 0
    updated_count = 0
    deleted_count = 0
    
    # Find all recurrences where next_occurrence date is exactly today
    # We need to filter by date, not datetime, since next_occurrence is stored in UTC
    # but we want to compare dates in Tallinn timezone
    from datetime import datetime as dt
    import pytz
    
    # Get all recurrences and filter by date in Python to avoid timezone issues
    all_recurrences = TaskRecurrence.objects.select_related(
        'task', 'task__family', 'task__assigned_to', 'task__created_by'
    ).all()
    
    # Filter recurrences where next_occurrence date is exactly today
    # Only process recurrences that are due today, not ones that are in the past
    due_recurrences = []
    for recurrence in all_recurrences:
        # Get the date part of next_occurrence (this handles timezone conversion correctly)
        next_date = recurrence.next_occurrence.date()
        if next_date == today:
            due_recurrences.append(recurrence)
    
    for recurrence in due_recurrences:
        # Store family and task name before we might delete the task
        # Get from recurrence.task if it exists, otherwise we can't process this recurrence
        if not recurrence.task:
            logger.warning(f"Recurrence {recurrence.id} has no task, skipping")
            continue
        
        task_family = recurrence.task.family
        task_name = recurrence.task.name
        task_description = recurrence.task.description
        task_created_by = recurrence.task.created_by
        task_priority = recurrence.task.priority
        task_points = recurrence.task.points
        
        # Check if end_date has passed
        if recurrence.end_date and recurrence.end_date < today:
            # Delete the recurrence and its task if it exists
            if recurrence.task:
                task_name_for_log = recurrence.task.name
                recurrence.task.delete()
            recurrence.delete()
            logger.info(
                f"Deleted expired recurrence for task '{task_name_for_log}' "
                f"(end date {recurrence.end_date} passed)"
            )
            continue
        
        # Get the current task referenced by this recurrence
        current_task = recurrence.task
        
        # If task is completed and approved, delete it and create a new one
        if current_task and current_task.completed and current_task.approved:
            logger.info(
                f"Task '{current_task.name}' (ID: {current_task.id}) is completed and approved, "
                f"deleting and creating new one for {today}"
            )
            # Store old task ID for deletion
            old_task_id = current_task.id
            
            # Create new task for today FIRST (before deleting old one)
            # This ensures recurrence.task is never None (CASCADE would delete recurrence if task is deleted)
            new_task = Task.objects.create(
                name=task_name,
                description=task_description,
                family=task_family,
                assigned_to=None,
                created_by=task_created_by,
                due_date=today,
                priority=task_priority,
                points=task_points,
                completed=False,
                completed_by=None,
                completed_at=None,
                approved=False,
                approved_by=None,
                approved_at=None,
                started_at=None,
            )
            created_count += 1
            
            # Update recurrence to point to new task BEFORE deleting old task
            # This prevents CASCADE from deleting the recurrence
            recurrence.task = new_task
            
            # Calculate and update next occurrence
            next_due_date, next_occurrence = calculate_next_occurrence(
                today, recurrence.frequency, recurrence.interval,
                day_of_week=recurrence.day_of_week,
                day_of_month=recurrence.day_of_month
            )
            recurrence.next_occurrence = next_occurrence
            recurrence.save()
            
            # Now delete the old task (recurrence is already pointing to new task, so CASCADE won't affect it)
            Task.objects.filter(id=old_task_id).delete()
            deleted_count += 1
            
            logger.info(
                f"Created new task '{new_task.name}' (ID: {new_task.id}) for {today} "
                f"to replace completed task (deleted old task {old_task_id})"
            )
            
            # Continue to next recurrence
            continue
        
        # Check if task for today already exists (excluding the current task if it's not for today)
        existing_task_today = None
        if current_task and current_task.due_date == today:
            # Current task is for today, use it
            existing_task_today = current_task
        else:
            # Look for another task for today (only incomplete ones)
            existing_task_today = Task.objects.filter(
                family=task_family,
                name=task_name,
                due_date=today,
                completed=False
            ).exclude(id=current_task.id if current_task else None).first()
        
        # If we have an existing task for today, use it
        if existing_task_today:
            # Update recurrence to point to this task
            if recurrence.task != existing_task_today:
                recurrence.task = existing_task_today
                recurrence.save()
            # Task already exists for today, just update next_occurrence
            next_due_date, next_occurrence = calculate_next_occurrence(
                today, recurrence.frequency, recurrence.interval,
                day_of_week=recurrence.day_of_week,
                day_of_month=recurrence.day_of_month
            )
            recurrence.next_occurrence = next_occurrence
            recurrence.save()
            logger.info(
                f"Task '{existing_task_today.name}' (ID: {existing_task_today.id}) already exists for {today}, "
                f"updated next_occurrence to {next_occurrence.date()}"
            )
            continue
        
        # No task for today exists - need to create or update
        # Only update due_date if next_occurrence is exactly today (which we've already filtered for)
        if current_task and not current_task.completed:
            # Task exists but is not completed and due_date doesn't match today
            # Since next_occurrence is today, we should update the due_date to today
            if current_task.due_date != today:
                current_task.due_date = today
                current_task.assigned_to = None  # Reset assignment
                current_task.started_at = None  # Reset started_at
                current_task.save()
                updated_count += 1
                logger.info(
                    f"Updated due_date to {today} for existing task '{current_task.name}' (ID: {current_task.id})"
                )
        else:
            # Create new task for today
            # First, delete any old uncompleted tasks for this recurrence (same name, same family)
            old_tasks = Task.objects.filter(
                family=task_family,
                name=task_name,
                completed=False,
                due_date__lt=today
            )
            if old_tasks.exists():
                old_count, _ = old_tasks.delete()
                deleted_count += old_count
                logger.info(
                    f"Deleted {old_count} old uncompleted task(s) for '{task_name}' "
                    f"before creating new one for {today}"
                )
            
            # Create new task for today
            new_task = Task.objects.create(
                name=task_name,
                description=task_description,
                family=task_family,
                assigned_to=None,
                created_by=task_created_by,
                due_date=today,
                priority=task_priority,
                points=task_points,
                completed=False,
                completed_by=None,
                completed_at=None,
                approved=False,
                approved_by=None,
                approved_at=None,
                started_at=None,
            )
            created_count += 1
            
            # Update recurrence to point to new task
            recurrence.task = new_task
            logger.info(
                f"Created recurring task '{new_task.name}' (ID: {new_task.id}) for {today}"
            )
        
        # Calculate and update next occurrence
        next_due_date, next_occurrence = calculate_next_occurrence(
            today, recurrence.frequency, recurrence.interval,
            day_of_week=recurrence.day_of_week,
            day_of_month=recurrence.day_of_month
        )
        recurrence.next_occurrence = next_occurrence
        recurrence.save()
    
    logger.info(
        f"Recurring tasks processed: {created_count} created, {updated_count} updated, {deleted_count} deleted"
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
