import logging
from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from a_tasks.models import Task, TaskRecurrence

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Creates new task instances for recurring tasks that are due.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Perform a dry run without actually creating any tasks.',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        now = timezone.now()
        
        # Find all recurrences where next_occurrence is in the past or today
        # We check for tasks that should have been created by now
        due_recurrences = TaskRecurrence.objects.filter(
            next_occurrence__lte=now
        ).select_related('task', 'task__family', 'task__assigned_to', 'task__created_by')
        
        created_count = 0
        
        for recurrence in due_recurrences:
            # Check if end_date has passed
            if recurrence.end_date and recurrence.end_date < now.date():
                if dry_run:
                    self.stdout.write(
                        f"DRY RUN: Would skip recurrence for task '{recurrence.task.name}' "
                        f"(ID: {recurrence.task.id}) - end date {recurrence.end_date} has passed"
                    )
                else:
                    # Delete the recurrence as it's expired
                    recurrence.delete()
                    logger.info(
                        f"Deleted expired recurrence for task '{recurrence.task.name}' "
                        f"(ID: {recurrence.task.id}) - end date {recurrence.end_date} passed"
                    )
                continue
            
            # Only create new task if the original task is completed
            # (The signal handles creating tasks when completed, but this handles
            # cases where tasks should be created on schedule even if previous wasn't completed)
            # Actually, let's create tasks based on the schedule regardless
            
            # Calculate the due date for the new task
            new_due_date = recurrence.next_occurrence.date()
            
            # Check if a task with this name and due date already exists for this family
            # (to avoid duplicates)
            existing_task = Task.objects.filter(
                family=recurrence.task.family,
                name=recurrence.task.name,
                due_date=new_due_date,
                completed=False
            ).first()
            
            if existing_task:
                # Task already exists, just update the recurrence
                if dry_run:
                    self.stdout.write(
                        f"DRY RUN: Task '{recurrence.task.name}' already exists for {new_due_date}, "
                        f"would update recurrence next_occurrence"
                    )
                else:
                    # Update recurrence next_occurrence
                    if recurrence.frequency == TaskRecurrence.FREQUENCY_DAILY:
                        recurrence.next_occurrence = timezone.now() + timedelta(days=1)
                    elif recurrence.frequency == TaskRecurrence.FREQUENCY_WEEKLY:
                        recurrence.next_occurrence = timezone.now() + timedelta(days=7)
                    elif recurrence.frequency == TaskRecurrence.FREQUENCY_MONTHLY:
                        recurrence.next_occurrence = timezone.now() + timedelta(days=30)
                    recurrence.save()
                continue
            
            # Create new task instance
            new_task = Task(
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
            
            if dry_run:
                self.stdout.write(
                    f"DRY RUN: Would create task '{new_task.name}' "
                    f"for recurrence (original task ID: {recurrence.task.id}) "
                    f"with due date {new_due_date}"
                )
            else:
                new_task.save()
                created_count += 1
                
                # Update recurrence next_occurrence
                if recurrence.frequency == TaskRecurrence.FREQUENCY_DAILY:
                    recurrence.next_occurrence = timezone.now() + timedelta(days=1)
                elif recurrence.frequency == TaskRecurrence.FREQUENCY_WEEKLY:
                    recurrence.next_occurrence = timezone.now() + timedelta(days=7)
                elif recurrence.frequency == TaskRecurrence.FREQUENCY_MONTHLY:
                    recurrence.next_occurrence = timezone.now() + timedelta(days=30)
                
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
        
        if dry_run:
            self.stdout.write(
                self.style.WARNING(
                    f"DRY RUN: Would create {created_count} recurring task(s)."
                )
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(
                    f"Successfully created {created_count} recurring task(s)."
                )
            )

