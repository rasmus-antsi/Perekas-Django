"""
Daily maintenance command - can be run manually for testing.
The scheduler runs this automatically at 00:00 Tallinn time.
"""
from django.core.management.base import BaseCommand
from django.utils import timezone
from a_tasks.maintenance import create_recurring_tasks_for_today, delete_completed_tasks, clear_shopping_cart


class Command(BaseCommand):
    help = 'Daily maintenance: creates recurring tasks for today and deletes completed tasks'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Perform a dry run without actually making changes.',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        today = timezone.now().date()
        
        self.stdout.write(f"Running daily maintenance for {today}...")
        
        if dry_run:
            self.stdout.write(
                self.style.WARNING("DRY RUN: No changes will be made")
            )
            # In dry run, we'd need to modify the functions to not actually save
            # For now, just show what would happen
            self.stdout.write("Would create recurring tasks for today")
            self.stdout.write("Would delete all completed tasks")
            self.stdout.write("Would clear shopping cart")
            return
        
        # 1. Create recurring tasks for today
        created_count = create_recurring_tasks_for_today(today)
        
        # 2. Delete completed tasks
        deleted_count = delete_completed_tasks()
        
        # 3. Clear shopping cart
        cart_cleared_count = clear_shopping_cart()
        
        self.stdout.write(
            self.style.SUCCESS(
                f"Successfully created {created_count} recurring task(s), "
                f"deleted {deleted_count} completed task(s), and "
                f"cleared {cart_cleared_count} item(s) from shopping cart."
            )
        )
