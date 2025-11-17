from django.contrib.auth.models import User
from django.db import models
from django.utils import timezone
from datetime import date


class Subscription(models.Model):
    TIER_FREE = 'FREE'
    TIER_STARTER = 'STARTER'
    TIER_PRO = 'PRO'
    TIER_CHOICES = [
        (TIER_FREE, 'Free'),
        (TIER_STARTER, 'Starter'),
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
        (STATUS_ACTIVE, 'Active'),
        (STATUS_CANCELLED, 'Cancelled'),
        (STATUS_PAST_DUE, 'Past Due'),
        (STATUS_INCOMPLETE, 'Incomplete'),
        (STATUS_INCOMPLETE_EXPIRED, 'Incomplete Expired'),
        (STATUS_TRIALING, 'Trialing'),
        (STATUS_UNPAID, 'Unpaid'),
    ]

    owner = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='subscriptions'
    )
    tier = models.CharField(max_length=10, choices=TIER_CHOICES, default=TIER_FREE)
    stripe_subscription_id = models.CharField(max_length=255, null=True, blank=True)
    stripe_customer_id = models.CharField(max_length=255, null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_ACTIVE)
    current_period_start = models.DateTimeField(null=True, blank=True)
    current_period_end = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.owner.username} - {self.get_tier_display()} ({self.get_status_display()})'

    def is_active(self):
        """Check if subscription is currently active"""
        if self.tier == self.TIER_FREE:
            return True
        return self.status == self.STATUS_ACTIVE or self.status == self.STATUS_TRIALING


class SubscriptionUsage(models.Model):
    """Track monthly usage of tasks and rewards per family"""
    family = models.ForeignKey(
        'a_family.Family',
        on_delete=models.CASCADE,
        related_name='subscription_usage'
    )
    month = models.DateField()  # First day of the month
    tasks_created = models.PositiveIntegerField(default=0)
    rewards_created = models.PositiveIntegerField(default=0)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ['family', 'month']
        ordering = ['-month']

    def __str__(self):
        return f'{self.family.name} - {self.month.strftime("%B %Y")}'
