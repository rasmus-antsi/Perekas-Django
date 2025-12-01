from django.core.management.base import BaseCommand
from django.db.models import Count, Q
from django.utils import timezone
from datetime import timedelta
from a_subscription.models import SubscriptionUsage


class Command(BaseCommand):
    help = 'Clean up duplicate SubscriptionUsage records, keeping the one with the highest values'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be deleted without actually deleting',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        
        # First, find exact duplicates
        exact_duplicates = (
            SubscriptionUsage.objects
            .values('family', 'period_start')
            .annotate(count=Count('id'))
            .filter(count__gt=1)
        )
        
        # Also find near-duplicates (same family, period_start within 1 minute)
        # Group by family and normalized period_start (rounded to minute)
        all_records = SubscriptionUsage.objects.all().order_by('family', 'period_start')
        
        # Group records by family and normalized period_start
        grouped = {}
        for record in all_records:
            # Normalize period_start to minute precision
            normalized = record.period_start.replace(second=0, microsecond=0)
            key = (record.family_id, normalized)
            
            if key not in grouped:
                grouped[key] = []
            grouped[key].append(record)
        
        # Find groups with multiple records
        duplicate_groups = {k: v for k, v in grouped.items() if len(v) > 1}
        
        if not duplicate_groups:
            self.stdout.write(self.style.SUCCESS('No duplicate records found.'))
            return
        
        self.stdout.write(f'Found {len(duplicate_groups)} duplicate group(s).')
        
        total_deleted = 0
        
        for (family_id, normalized_period), records in duplicate_groups.items():
            # Sort records: keep the one with highest values or most recent
            records_sorted = sorted(
                records,
                key=lambda r: (
                    -r.tasks_created,
                    -r.rewards_created,
                    -r.recurring_tasks_created,
                    -r.updated_at.timestamp() if r.updated_at else 0
                )
            )
            
            keep_record = records_sorted[0]
            delete_records = records_sorted[1:]
            
            self.stdout.write(
                f'\nFamily: {keep_record.family.name}, Period: {normalized_period}'
            )
            self.stdout.write(
                f'  Keeping: ID {keep_record.id} (period_start={keep_record.period_start}, '
                f'tasks={keep_record.tasks_created}, '
                f'rewards={keep_record.rewards_created}, '
                f'recurring={keep_record.recurring_tasks_created})'
            )
            
            # Merge values: take the maximum of each field
            for record in delete_records:
                self.stdout.write(
                    f'  {"Would delete" if dry_run else "Deleting"}: ID {record.id} '
                    f'(period_start={record.period_start}, tasks={record.tasks_created}, '
                    f'rewards={record.rewards_created}, '
                    f'recurring={record.recurring_tasks_created})'
                )
                
                # Merge values into keep_record
                keep_record.tasks_created = max(keep_record.tasks_created, record.tasks_created)
                keep_record.rewards_created = max(keep_record.rewards_created, record.rewards_created)
                keep_record.recurring_tasks_created = max(
                    keep_record.recurring_tasks_created, 
                    record.recurring_tasks_created
                )
            
            if not dry_run:
                # Normalize period_start to minute precision
                keep_record.period_start = normalized_period
                keep_record.save()
                
                # Delete duplicates
                for record in delete_records:
                    record.delete()
                    total_deleted += 1
                
                self.stdout.write(
                    self.style.SUCCESS(
                        f'  Merged and deleted {len(delete_records)} duplicate(s). '
                        f'Final values: tasks={keep_record.tasks_created}, '
                        f'rewards={keep_record.rewards_created}, '
                        f'recurring={keep_record.recurring_tasks_created}'
                    )
                )
        
        if dry_run:
            would_delete = sum(len(records) - 1 for records in duplicate_groups.values())
            self.stdout.write(
                self.style.WARNING(
                    f'\nDRY RUN: Would delete {would_delete} duplicate record(s). '
                    'Run without --dry-run to actually delete.'
                )
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(
                    f'\nSuccessfully deleted {total_deleted} duplicate record(s).'
                )
            )

