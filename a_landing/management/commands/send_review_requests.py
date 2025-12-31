"""
Management command to send review request emails to users who created accounts
but haven't used the app (no family members, no tasks, no rewards, no shopping lists).

Usage:
    python manage.py send_review_requests
    python manage.py send_review_requests --days 7  # Only users who signed up 7+ days ago
    python manage.py send_review_requests --dry-run  # Preview without sending
"""
from django.core.management.base import BaseCommand
from django.test import RequestFactory
from django.utils import timezone
from datetime import timedelta

from a_family.models import User, Family
from a_family.emails import send_review_request_email
from a_tasks.models import Task
from a_rewards.models import Reward
from a_shopping.models import ShoppingListItem


class Command(BaseCommand):
    help = 'Send review request emails to users who created accounts but haven\'t used the app'

    def add_arguments(self, parser):
        parser.add_argument(
            '--days',
            type=int,
            default=3,
            help='Only send to users who signed up at least N days ago (default: 3)',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be sent without actually sending',
        )

    def handle(self, *args, **options):
        days = options['days']
        dry_run = options['dry_run']
        
        # Calculate cutoff date
        cutoff_date = timezone.now() - timedelta(days=days)
        
        # Find users who:
        # 1. Have email addresses
        # 2. Signed up at least N days ago
        # 3. Are parents (children usually don't create accounts themselves)
        # 4. Haven't added family members OR haven't created any content
        
        users = User.objects.filter(
            email__isnull=False
        ).exclude(
            email=''
        ).filter(
            role=User.ROLE_PARENT,
            created_at__lte=cutoff_date
        )
        
        inactive_users = []
        
        for user in users:
            # Check if user has a family
            family = Family.objects.filter(owner=user).first() or user.families.first()
            
            if not family:
                # No family at all - definitely inactive
                inactive_users.append(user)
                continue
            
            # Check if family has members (other than owner)
            member_count = family.members.exclude(id=user.id).count()
            
            # Check if user has created any content
            tasks_created = Task.objects.filter(family=family, created_by=user).exists()
            rewards_created = Reward.objects.filter(family=family, created_by=user).exists()
            shopping_items = ShoppingListItem.objects.filter(family=family, added_by=user).exists()
            
            # If no members AND no content created, consider inactive
            if member_count == 0 and not tasks_created and not rewards_created and not shopping_items:
                inactive_users.append(user)
        
        if not inactive_users:
            self.stdout.write(self.style.SUCCESS(f"No inactive users found (signed up {days}+ days ago)."))
            return
        
        self.stdout.write(f"\nFound {len(inactive_users)} inactive user(s) (signed up {days}+ days ago):")
        for user in inactive_users[:20]:  # Show first 20
            family = Family.objects.filter(owner=user).first() or user.families.first()
            has_family = "Has family" if family else "No family"
            self.stdout.write(f"  - {user.email} ({user.get_display_name()}) - {has_family}")
        if len(inactive_users) > 20:
            self.stdout.write(f"  ... and {len(inactive_users) - 20} more")
        
        if dry_run:
            self.stdout.write(self.style.WARNING("\nDRY RUN - No emails will be sent"))
            return
        
        # Confirm before sending
        self.stdout.write(f"\nAbout to send review request emails to {len(inactive_users)} user(s).")
        confirm = input("Are you sure you want to proceed? [y/N]: ")
        if confirm.lower() != 'y':
            self.stdout.write(self.style.WARNING("Cancelled."))
            return
        
        # Create a mock request for building URLs
        factory = RequestFactory()
        request = factory.get('/', SERVER_NAME='perekas.ee')
        request.META['HTTP_X_FORWARDED_PROTO'] = 'https'
        request.META['wsgi.url_scheme'] = 'https'
        
        # Send emails
        self.stdout.write("Sending emails...")
        sent_count = 0
        skipped_count = 0
        
        for user in inactive_users:
            try:
                send_review_request_email(request, user)
                sent_count += 1
                self.stdout.write(f"  ✓ Sent to {user.email}")
            except Exception as e:
                skipped_count += 1
                self.stdout.write(self.style.ERROR(f"  ✗ Failed to send to {user.email}: {e}"))
        
        self.stdout.write(
            self.style.SUCCESS(
                f"\nSuccessfully sent {sent_count} email(s). Skipped {skipped_count}."
            )
        )

