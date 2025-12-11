"""
Management command to clean up duplicate recurring tasks in the database.
This should be run once to fix existing duplicates, then the maintenance logic
will prevent new duplicates from being created.
"""
from django.core.management.base import BaseCommand
from django.db.models import Count
from django.utils import timezone
from a_tasks.models import Task, TaskRecurrence
from datetime import date


class Command(BaseCommand):
    help = 'Clean up duplicate recurring tasks in the database'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Perform a dry run without actually making changes.',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        today = timezone.now().date()
        
        self.stdout.write(f"Cleaning up duplicate recurring tasks (today={today})...")
        
        if dry_run:
            self.stdout.write(
                self.style.WARNING("DRY RUN: No changes will be made")
            )
        
        # Find all recurrences
        recurrences = TaskRecurrence.objects.select_related('task', 'task__family').all()
        
        total_deleted = 0
        total_updated = 0
        
        for recurrence in recurrences:
            if not recurrence.task:
                continue
            
            family = recurrence.task.family
            task_name = recurrence.task.name
            
            # Find all tasks for this recurrence (same family, same name)
            all_tasks = Task.objects.filter(
                family=family,
                name=task_name
            ).order_by('due_date', 'id')
            
            # Group by due_date to find duplicates
            tasks_by_date = {}
            for task in all_tasks:
                if task.due_date not in tasks_by_date:
                    tasks_by_date[task.due_date] = []
                tasks_by_date[task.due_date].append(task)
            
            # For each due_date, keep only one task (prefer the one referenced by recurrence)
            for due_date, tasks in tasks_by_date.items():
                if len(tasks) > 1:
                    # Find the task referenced by recurrence
                    recurrence_task = None
                    for task in tasks:
                        if task.id == recurrence.task.id:
                            recurrence_task = task
                            break
                    
                    # Keep the recurrence task, or the first one if recurrence doesn't point to any
                    if recurrence_task:
                        task_to_keep = recurrence_task
                    else:
                        # Prefer incomplete tasks, then by ID
                        incomplete_tasks = [t for t in tasks if not t.completed]
                        if incomplete_tasks:
                            task_to_keep = incomplete_tasks[0]
                        else:
                            task_to_keep = tasks[0]
                    
                    # Delete duplicates
                    tasks_to_delete = [t for t in tasks if t.id != task_to_keep.id]
                    if tasks_to_delete:
                        if not dry_run:
                            deleted_count, _ = Task.objects.filter(
                                id__in=[t.id for t in tasks_to_delete]
                            ).delete()
                            total_deleted += deleted_count
                            
                            # Update recurrence to point to the kept task if needed
                            if recurrence.task != task_to_keep:
                                recurrence.task = task_to_keep
                                recurrence.save()
                                total_updated += 1
                        
                        self.stdout.write(
                            f"  Found {len(tasks)} tasks for '{task_name}' on {due_date}, "
                            f"keeping task {task_to_keep.id}, deleting {len(tasks_to_delete)} duplicate(s)"
                        )
        
        # Also fix recurrences that point to tasks with wrong due_date
        for recurrence in recurrences:
            if not recurrence.task:
                continue
            
            expected_due_date = recurrence.next_occurrence.date()
            if recurrence.task.due_date != expected_due_date:
                # Check if there's already a task for the expected due_date
                existing_task = Task.objects.filter(
                    family=recurrence.task.family,
                    name=recurrence.task.name,
                    due_date=expected_due_date
                ).exclude(id=recurrence.task.id).first()
                
                if existing_task:
                    # Point recurrence to the correct task
                    if not dry_run:
                        recurrence.task = existing_task
                        recurrence.save()
                        total_updated += 1
                    self.stdout.write(
                        f"  Updated recurrence {recurrence.id} to point to task {existing_task.id} "
                        f"(due_date={expected_due_date})"
                    )
                elif recurrence.task.due_date < expected_due_date:
                    # Update task due_date to match recurrence
                    if not dry_run:
                        recurrence.task.due_date = expected_due_date
                        recurrence.task.save()
                        total_updated += 1
                    self.stdout.write(
                        f"  Updated task {recurrence.task.id} due_date from {recurrence.task.due_date} "
                        f"to {expected_due_date}"
                    )
        
        if dry_run:
            self.stdout.write(
                self.style.WARNING(
                    f"DRY RUN: Would delete {total_deleted} duplicate task(s) and "
                    f"update {total_updated} recurrence(s)/task(s)"
                )
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(
                    f"Successfully deleted {total_deleted} duplicate task(s) and "
                    f"updated {total_updated} recurrence(s)/task(s)"
                )
            )

