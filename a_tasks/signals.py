import logging
from django.db.models.signals import pre_save, post_save
from django.dispatch import receiver
from django.utils import timezone
from datetime import timedelta
from .models import Task, TaskRecurrence

logger = logging.getLogger(__name__)

# Store the previous state to detect when a task transitions to completed
_previous_task_state = {}


@receiver(pre_save, sender=Task)
def store_task_state(sender, instance, **kwargs):
    """Store the previous state of the task before saving"""
    if instance.pk:
        try:
            old_instance = Task.objects.get(pk=instance.pk)
            _previous_task_state[instance.pk] = {
                'completed': old_instance.completed,
                'completed_at': old_instance.completed_at,
            }
        except Task.DoesNotExist:
            _previous_task_state[instance.pk] = {
                'completed': False,
                'completed_at': None,
            }


@receiver(post_save, sender=Task)
def auto_delete_old_completed_tasks(sender, instance, created, **kwargs):
    """
    Automatically delete tasks that have been completed for 48+ hours.
    Only runs when a task transitions from not completed to completed.
    """
    # Check if this task was just completed (transition from False to True)
    was_just_completed = False
    
    if created:
        # New task that's being created as completed
        was_just_completed = instance.completed and instance.completed_at is not None
    elif instance.pk in _previous_task_state:
        # Existing task - check if it transitioned to completed
        previous = _previous_task_state[instance.pk]
        was_just_completed = (
            not previous['completed'] and 
            instance.completed and 
            instance.completed_at is not None
        )
        # Clean up the stored state
        del _previous_task_state[instance.pk]
    
    # Safety: Clean up dictionary if it grows too large (shouldn't happen, but just in case)
    if len(_previous_task_state) > 1000:
        _previous_task_state.clear()
        logger.warning("Cleared _previous_task_state dictionary to prevent memory leak")
    
    # Only run cleanup when a task is actually being completed
    if was_just_completed:
        try:
            # Handle recurring tasks - create next occurrence when task is completed
            recurrences = TaskRecurrence.objects.filter(task=instance)
            for recurrence in recurrences:
                try:
                    from .recurrence_utils import calculate_next_occurrence
                    
                    # Calculate next occurrence based on due_date (recurring starts from due date)
                    # Use the current task's due_date as the base
                    base_due_date = instance.due_date
                    if not base_due_date:
                        # If no due date, use today
                        base_due_date = timezone.now().date()
                    
                    next_due_date, next_occurrence = calculate_next_occurrence(
                        base_due_date, recurrence.frequency, recurrence.interval,
                        day_of_week=recurrence.day_of_week,
                        day_of_month=recurrence.day_of_month
                    )
                    
                    # Check if recurrence has ended
                    if recurrence.end_date:
                        if next_due_date > recurrence.end_date:
                            # Recurrence has ended, delete it
                            recurrence.delete()
                            continue
                    
                    # Create new task instance
                    new_task = Task.objects.create(
                        name=instance.name,
                        description=instance.description,
                        family=instance.family,
                        assigned_to=instance.assigned_to,
                        created_by=instance.created_by,
                        due_date=next_due_date,
                        priority=instance.priority,
                        points=instance.points,
                        completed=False,
                        approved=False,
                    )
                    
                    # Update recurrence to point to new task (preserve day_of_week and day_of_month)
                    recurrence.task = new_task
                    recurrence.next_occurrence = next_occurrence
                    recurrence.save()
                    
                    logger.info(f"Created recurring task '{new_task.name}' (next: {next_occurrence.date()})")
                except Exception as e:
                    logger.error(f"Error creating recurring task: {e}", exc_info=True)
            
            # Calculate the cutoff time (48 hours ago)
            cutoff_time = timezone.now() - timedelta(hours=48)
            
            # Find and delete tasks that were completed more than 48 hours ago
            # Exclude the current task (in case it was just completed)
            old_tasks = Task.objects.filter(
                completed=True,
                completed_at__isnull=False,
                completed_at__lt=cutoff_time
            ).exclude(id=instance.id)
            
            deleted_count, _ = old_tasks.delete()
            
            if deleted_count > 0:
                logger.info(f"Auto-deleted {deleted_count} task(s) that were completed 48+ hours ago")
        except Exception as e:
            # Log error but don't break the task completion flow
            logger.error(f"Error auto-deleting old completed tasks: {e}", exc_info=True)

