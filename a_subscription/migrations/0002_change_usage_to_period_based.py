# Generated migration to change usage tracking from calendar month to subscription period

from django.db import migrations, models
from django.utils import timezone
from datetime import datetime


def migrate_month_to_period_start(apps, schema_editor):
    """
    Migrate existing data from 'month' (DateField) to 'period_start' (DateTimeField).
    For existing records, convert the month date to a datetime at midnight.
    """
    SubscriptionUsage = apps.get_model('a_subscription', 'SubscriptionUsage')
    
    for usage in SubscriptionUsage.objects.all():
        # Convert DateField to DateTimeField at midnight
        if usage.month:
            usage.period_start = timezone.make_aware(
                datetime.combine(usage.month, datetime.min.time())
            )
            usage.save()


def reverse_migrate_period_start_to_month(apps, schema_editor):
    """
    Reverse migration: convert period_start back to month (date only).
    """
    SubscriptionUsage = apps.get_model('a_subscription', 'SubscriptionUsage')
    
    for usage in SubscriptionUsage.objects.all():
        if usage.period_start:
            usage.month = usage.period_start.date()
            usage.save()


class Migration(migrations.Migration):

    dependencies = [
        ('a_subscription', '0001_initial'),
    ]

    operations = [
        # Step 1: Add period_start as nullable field
        migrations.AddField(
            model_name='subscriptionusage',
            name='period_start',
            field=models.DateTimeField(db_index=True, null=True, blank=True),
        ),
        
        # Step 2: Migrate data from month to period_start
        migrations.RunPython(migrate_month_to_period_start, reverse_migrate_period_start_to_month),
        
        # Step 3: Remove the index on (family, month) BEFORE removing the field
        migrations.RemoveIndex(
            model_name='subscriptionusage',
            name='subscriptio_family__96b583_idx',
        ),
        
        # Step 4: Remove unique_together constraint on (family, month)
        migrations.AlterUniqueTogether(
            name='subscriptionusage',
            unique_together=set(),
        ),
        
        # Step 5: Make period_start non-nullable
        migrations.AlterField(
            model_name='subscriptionusage',
            name='period_start',
            field=models.DateTimeField(db_index=True),
        ),
        
        # Step 6: Remove the month field (index is already removed)
        migrations.RemoveField(
            model_name='subscriptionusage',
            name='month',
        ),
        
        # Step 7: Add new unique_together constraint on (family, period_start)
        migrations.AlterUniqueTogether(
            name='subscriptionusage',
            unique_together={('family', 'period_start')},
        ),
        
        # Step 8: Add new index on (family, period_start)
        migrations.AddIndex(
            model_name='subscriptionusage',
            index=models.Index(fields=['family', 'period_start'], name='subscriptio_family__period_idx'),
        ),
        
        # Step 9: Update ordering
        migrations.AlterModelOptions(
            name='subscriptionusage',
            options={
                'verbose_name': 'subscription usage',
                'verbose_name_plural': 'subscription usages',
                'db_table': 'subscription_subscriptionusage',
                'ordering': ['-period_start'],
            },
        ),
    ]

