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
def cleanup_previous_task_state(sender, instance, created, **kwargs):
    """
    Cleanup function to remove stored state after task save.
    Recurring tasks are now handled by the daily maintenance job, not on completion.
    """
    # Clean up the stored state
    if instance.pk in _previous_task_state:
        del _previous_task_state[instance.pk]
    
    # Safety: Clean up dictionary if it grows too large (shouldn't happen, but just in case)
    if len(_previous_task_state) > 1000:
        _previous_task_state.clear()
        logger.warning("Cleared _previous_task_state dictionary to prevent memory leak")

