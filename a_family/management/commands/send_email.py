"""
Management command to send bulk emails using EmailTemplate.

Usage examples:
    python manage.py send_email --template welcome_back --all
    python manage.py send_email --template promo --filter parents
    python manage.py send_email --template update --filter children
    python manage.py send_email --template welcome_back --family <uuid>
    python manage.py send_email --template promo --all --dry-run
    python manage.py send_email --list  # List all available templates
"""
from django.core.management.base import BaseCommand, CommandError

from a_family.models import User, Family, EmailTemplate
from a_family.emails import send_bulk_email


class Command(BaseCommand):
    help = 'Send bulk emails using an EmailTemplate to all or filtered users'

    def add_arguments(self, parser):
        parser.add_argument(
            '--template',
            type=str,
            help='Name of the EmailTemplate to use',
        )
        parser.add_argument(
            '--all',
            action='store_true',
            help='Send to all users with email addresses',
        )
        parser.add_argument(
            '--filter',
            type=str,
            choices=['parents', 'children'],
            help='Filter users by role (parents or children)',
        )
        parser.add_argument(
            '--family',
            type=str,
            help='Filter users by family UUID (members + owner)',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be sent without actually sending',
        )
        parser.add_argument(
            '--list',
            action='store_true',
            help='List all available email templates',
        )
        parser.add_argument(
            '--base-url',
            type=str,
            default='https://perekas.ee',
            help='Base URL for building absolute URLs (default: https://perekas.ee)',
        )

    def handle(self, *args, **options):
        # List templates mode
        if options['list']:
            self._list_templates()
            return
        
        # Validate arguments
        if not options['template']:
            raise CommandError("You must provide --template or use --list to see available templates")
        
        if not options['all'] and not options['filter'] and not options['family']:
            raise CommandError("You must specify --all, --filter, or --family to select recipients")
        
        # Get template
        try:
            template = EmailTemplate.objects.get(name=options['template'])
        except EmailTemplate.DoesNotExist:
            raise CommandError(f"EmailTemplate '{options['template']}' not found. Use --list to see available templates.")
        
        if not template.is_active:
            raise CommandError(f"EmailTemplate '{template.name}' is not active. Activate it in the admin first.")
        
        # Build user queryset
        users = User.objects.filter(email__isnull=False).exclude(email='')
        
        if options['filter']:
            if options['filter'] == 'parents':
                users = users.filter(role=User.ROLE_PARENT)
            elif options['filter'] == 'children':
                users = users.filter(role=User.ROLE_CHILD)
        
        if options['family']:
            try:
                family = Family.objects.get(id=options['family'])
            except Family.DoesNotExist:
                raise CommandError(f"Family with ID '{options['family']}' not found.")
            except Exception:
                raise CommandError(f"Invalid family UUID: '{options['family']}'")
            
            # Get all users in this family (owner + members)
            family_user_ids = list(family.members.values_list('id', flat=True)) + [family.owner_id]
            users = users.filter(id__in=family_user_ids)
        
        user_list = list(users)
        user_count = len(user_list)
        
        if user_count == 0:
            self.stdout.write(self.style.WARNING("No users match the specified criteria."))
            return
        
        # Dry run mode
        if options['dry_run']:
            self.stdout.write(self.style.WARNING("DRY RUN - No emails will be sent"))
            self.stdout.write(f"\nTemplate: {template.name}")
            self.stdout.write(f"Subject: {template.subject}")
            self.stdout.write(f"\nWould send to {user_count} user(s):")
            for user in user_list[:20]:  # Show first 20
                self.stdout.write(f"  - {user.email} ({user.get_display_name()}, {user.get_role_display()})")
            if user_count > 20:
                self.stdout.write(f"  ... and {user_count - 20} more")
            return
        
        # Confirm before sending
        self.stdout.write(f"\nAbout to send '{template.subject}' to {user_count} user(s).")
        confirm = input("Are you sure you want to proceed? [y/N]: ")
        if confirm.lower() != 'y':
            self.stdout.write(self.style.WARNING("Cancelled."))
            return
        
        # Send emails
        self.stdout.write(f"Sending emails...")
        sent_count, skipped_count = send_bulk_email(
            template, 
            user_list,
            base_url=options['base_url']
        )
        
        self.stdout.write(
            self.style.SUCCESS(
                f"Successfully sent {sent_count} email(s). Skipped {skipped_count} (no email address)."
            )
        )
    
    def _list_templates(self):
        """List all available email templates."""
        templates = EmailTemplate.objects.all()
        
        if not templates.exists():
            self.stdout.write(self.style.WARNING("No email templates found. Create one in the Django admin."))
            return
        
        self.stdout.write("\nAvailable Email Templates:")
        self.stdout.write("-" * 60)
        
        for template in templates:
            status = self.style.SUCCESS("ACTIVE") if template.is_active else self.style.ERROR("INACTIVE")
            self.stdout.write(f"\n  Name: {template.name}")
            self.stdout.write(f"  Subject: {template.subject}")
            self.stdout.write(f"  Status: {status}")
            self.stdout.write(f"  Updated: {template.updated_at.strftime('%Y-%m-%d %H:%M')}")
        
        self.stdout.write("\n" + "-" * 60)
        self.stdout.write("\nUsage: python manage.py send_email --template <name> --all")
