from django.db import models
from django.utils import timezone
from datetime import date


class Subscription(models.Model):
    TIER_FREE = 'FREE'
    TIER_STARTER = 'STARTER'
    TIER_PRO = 'PRO'
    TIER_CHOICES = [
        (TIER_FREE, 'Tasuta'),
        (TIER_STARTER, 'Alustaja'),
        (TIER_PRO, 'Pro'),
    ]

    STATUS_ACTIVE = 'active'
    STATUS_CANCELLED = 'cancelled'
    STATUS_PAST_DUE = 'past_due'
    STATUS_INCOMPLETE = 'incomplete'
    STATUS_INCOMPLETE_EXPIRED = 'incomplete_expired'
    STATUS_TRIALING = 'trialing'
    STATUS_UNPAID = 'unpaid'
    STATUS_CHOICES = [
        (STATUS_ACTIVE, 'Aktiivne'),
        (STATUS_CANCELLED, 'Tühistatud'),
        (STATUS_PAST_DUE, 'Makset ootel'),
        (STATUS_INCOMPLETE, 'Pooleli'),
        (STATUS_INCOMPLETE_EXPIRED, 'Pooleli – aegunud'),
        (STATUS_TRIALING, 'Prooviperioodil'),
        (STATUS_UNPAID, 'Maksmata'),
    ]

    owner = models.ForeignKey(
        'a_family.User',
        on_delete=models.CASCADE,
        related_name='subscriptions',
        db_index=True,
    )
    tier = models.CharField(max_length=10, choices=TIER_CHOICES, default=TIER_FREE, db_index=True)
    stripe_subscription_id = models.CharField(max_length=255, null=True, blank=True, db_index=True)
    stripe_customer_id = models.CharField(max_length=255, null=True, blank=True, db_index=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_ACTIVE, db_index=True)
    current_period_start = models.DateTimeField(null=True, blank=True)
    current_period_end = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'subscription_subscription'
        verbose_name = 'subscription'
        verbose_name_plural = 'subscriptions'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['owner', 'status']),
            models.Index(fields=['owner', 'tier']),
            models.Index(fields=['status', 'tier']),
        ]

    def __str__(self):
        return f'{self.owner.get_display_name()} - {self.get_tier_display()} ({self.get_status_display()})'

    def is_active(self):
        """Check if subscription is currently active"""
        if self.tier == self.TIER_FREE:
            return True
        return self.status == self.STATUS_ACTIVE or self.status == self.STATUS_TRIALING


class SubscriptionUsage(models.Model):
    """Track usage of tasks and rewards per family per subscription period"""
    family = models.ForeignKey(
        'a_family.Family',
        on_delete=models.CASCADE,
        related_name='subscription_usage',
        db_index=True,
    )
    period_start = models.DateTimeField(db_index=True)  # Start of the subscription period
    tasks_created = models.PositiveIntegerField(default=0)
    rewards_created = models.PositiveIntegerField(default=0)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'subscription_subscriptionusage'
        verbose_name = 'subscription usage'
        verbose_name_plural = 'subscription usages'
        unique_together = ['family', 'period_start']
        ordering = ['-period_start']
        indexes = [
            models.Index(fields=['family', 'period_start']),
        ]

    def __str__(self):
        return f'{self.family.name} - {self.period_start.strftime("%Y-%m-%d %H:%M")}'
