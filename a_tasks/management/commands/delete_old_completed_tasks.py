from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from a_tasks.models import Task


class Command(BaseCommand):
    help = 'Deletes tasks that have been completed for 48 hours or more'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be deleted without actually deleting',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        
        # Calculate the cutoff time (48 hours ago)
        cutoff_time = timezone.now() - timedelta(hours=48)
        
        # Find tasks that are completed and were completed more than 48 hours ago
        old_tasks = Task.objects.filter(
            completed=True,
            completed_at__isnull=False,
            completed_at__lt=cutoff_time
        )
        
        count = old_tasks.count()
        
        if count == 0:
            self.stdout.write(
                self.style.SUCCESS('No tasks found that have been completed for 48+ hours.')
            )
            return
        
        if dry_run:
            self.stdout.write(
                self.style.WARNING(
                    f'DRY RUN: Would delete {count} task(s) completed before {cutoff_time.strftime("%Y-%m-%d %H:%M:%S")}'
                )
            )
            for task in old_tasks[:10]:  # Show first 10 as examples
                self.stdout.write(f'  - Task ID {task.id}: "{task.name}" (completed at {task.completed_at})')
            if count > 10:
                self.stdout.write(f'  ... and {count - 10} more')
        else:
            # Delete the tasks
            deleted_count, _ = old_tasks.delete()
            self.stdout.write(
                self.style.SUCCESS(
                    f'Successfully deleted {deleted_count} task(s) that were completed 48+ hours ago.'
                )
            )

