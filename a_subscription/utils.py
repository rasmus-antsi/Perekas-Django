from django.contrib.auth import get_user_model

User = get_user_model()
from django.utils import timezone
from datetime import date, timedelta
from django.conf import settings
from .models import Subscription, SubscriptionUsage


# Tier limits
TIER_LIMITS = {
    Subscription.TIER_FREE: {
        'max_parents': 1,
        'max_children': 1,
        'max_tasks_per_month': 5,
        'max_rewards_per_month': 3,
        'shopping_list_enabled': False,
    },
    Subscription.TIER_STARTER: {
        'max_parents': 2,
        'max_children': 2,
        'max_tasks_per_month': 20,  # TBD - reasonable default
        'max_rewards_per_month': 15,  # TBD - reasonable default
        'shopping_list_enabled': True,
    },
    Subscription.TIER_PRO: {
        'max_parents': 4,
        'max_children': 10,
        'max_tasks_per_month': 100,  # TBD - reasonable default
        'max_rewards_per_month': 50,  # TBD - reasonable default
        'shopping_list_enabled': True,
    },
}


def get_user_subscription(user):
    """
    Get active subscription for a user (family owner).
    Returns the subscription tier, defaulting to FREE if no active subscription exists.
    """
    if not user or not user.is_authenticated:
        return Subscription.TIER_FREE

    subscription = Subscription.objects.filter(
        owner=user,
        tier__in=[Subscription.TIER_STARTER, Subscription.TIER_PRO]
    ).first()

    if subscription and subscription.is_active():
        return subscription.tier
    return Subscription.TIER_FREE


def get_family_subscription(family):
    """
    Get subscription tier for a family via the family owner.
    Returns FREE if no active subscription exists.
    """
    if not family or not family.owner:
        return Subscription.TIER_FREE
    return get_user_subscription(family.owner)


def get_tier_limits(tier):
    """Get limits for a given subscription tier"""
    return TIER_LIMITS.get(tier, TIER_LIMITS[Subscription.TIER_FREE])


def get_current_period_start(family):
    """
    Get the start date of the current subscription period for a family.
    For paid subscriptions, uses current_period_start.
    For FREE tier, uses family creation date and calculates 30-day periods from there.
    
    Returns:
        datetime: The start of the current subscription period
    """
    if not family:
        return None
    
    # Get the family's subscription
    subscription = Subscription.objects.filter(
        owner=family.owner,
        tier__in=[Subscription.TIER_STARTER, Subscription.TIER_PRO]
    ).first()
    
    if subscription and subscription.is_active() and subscription.current_period_start:
        # Paid subscription - use the subscription period start
        return subscription.current_period_start
    
    # FREE tier - use family creation date as the base period start
    # Calculate which 30-day period we're in based on family creation
    family_created = family.created_at
    if not family_created:
        # Fallback to current time if created_at is somehow missing
        family_created = timezone.now()
    
    now = timezone.now()
    
    # Calculate how many 30-day periods have passed since family creation
    time_diff = now - family_created
    days_passed = time_diff.total_seconds() / 86400  # Convert to days
    periods_passed = int(days_passed / 30)
    
    # Calculate the start of the current period
    period_start = family_created + timedelta(days=periods_passed * 30)
    
    return period_start


def get_current_month_usage(family):
    """
    Get or create usage record for the current subscription period.
    Returns the SubscriptionUsage object for the current period.
    Uses subscription period start dates instead of calendar months.
    """
    if not family:
        return None

    period_start = get_current_period_start(family)
    if not period_start:
        return None

    usage, created = SubscriptionUsage.objects.get_or_create(
        family=family,
        period_start=period_start,
        defaults={
            'tasks_created': 0,
            'rewards_created': 0,
        }
    )
    return usage


def check_subscription_limit(family, resource_type, count=1):
    """
    Check if a family can create a resource based on subscription limits.
    
    Args:
        family: Family instance
        resource_type: 'tasks' or 'rewards'
        count: Number of resources to create (default 1)
    
    Returns:
        tuple: (can_create: bool, current_count: int, limit: int, tier: str)
    """
    if not family:
        return False, 0, 0, Subscription.TIER_FREE

    tier = get_family_subscription(family)
    limits = get_tier_limits(tier)

    if resource_type == 'tasks':
        limit = limits['max_tasks_per_month']
        usage = get_current_month_usage(family)
        current_count = usage.tasks_created if usage else 0
    elif resource_type == 'rewards':
        limit = limits['max_rewards_per_month']
        usage = get_current_month_usage(family)
        current_count = usage.rewards_created if usage else 0
    else:
        return False, 0, 0, tier

    can_create = (current_count + count) <= limit
    return can_create, current_count, limit, tier


def increment_usage(family, resource_type, count=1):
    """
    Increment the monthly usage counter for a family.
    
    Args:
        family: Family instance
        resource_type: 'tasks' or 'rewards'
        count: Number to increment (default 1)
    """
    if not family:
        return

    usage = get_current_month_usage(family)
    if not usage:
        return

    if resource_type == 'tasks':
        usage.tasks_created += count
        usage.save(update_fields=['tasks_created', 'updated_at'])
    elif resource_type == 'rewards':
        usage.rewards_created += count
        usage.save(update_fields=['rewards_created', 'updated_at'])


def can_add_member(family, role):
    """
    Check if a family can add a member with the given role.
    
    Args:
        family: Family instance
        role: 'parent' or 'child' (from User.ROLE_CHOICES)
    
    Returns:
        tuple: (can_add: bool, current_count: int, limit: int, tier: str)
    """
    if not family:
        return False, 0, 0, Subscription.TIER_FREE

    tier = get_family_subscription(family)
    limits = get_tier_limits(tier)

    from a_family.models import User

    if role == User.ROLE_PARENT:
        limit = limits['max_parents']
        # Count owner + members with parent role
        current_count = 1  # Owner is always a parent
        current_count += family.members.filter(role=User.ROLE_PARENT).count()
        # Don't double count owner if they're also in members
        if family.owner in family.members.all() and family.owner.role == User.ROLE_PARENT:
            current_count -= 1
    elif role == User.ROLE_CHILD:
        limit = limits['max_children']
        current_count = family.members.filter(role=User.ROLE_CHILD).count()
    else:
        return False, 0, 0, tier

    can_add = current_count < limit
    return can_add, current_count, limit, tier


def has_shopping_list_access(family):
    """
    Check if a family has access to the shopping list feature.
    
    Returns:
        bool: True if shopping list is enabled for the family's subscription tier
    """
    if not family:
        return False

    tier = get_family_subscription(family)
    limits = get_tier_limits(tier)
    return limits['shopping_list_enabled']


def get_tier_from_price_id(price_id):
    """
    Map Stripe price ID to subscription tier.
    This is a scalable approach - easy to add new tiers in the future.
    
    Args:
        price_id: Stripe price ID string
    
    Returns:
        str: Subscription tier (FREE, STARTER, PRO) or None if not found
    """
    if not price_id:
        return None
    
    # Get price IDs from settings
    starter_monthly = getattr(settings, 'STARTER_MONTHLY_PRICE_ID', None)
    starter_yearly = getattr(settings, 'STARTER_YEARLY_PRICE_ID', None)
    pro_monthly = getattr(settings, 'PRO_MONTHLY_PRICE_ID', None)
    pro_yearly = getattr(settings, 'PRO_YEARLY_PRICE_ID', None)
    
    # Map price ID to tier
    if price_id == starter_monthly or price_id == starter_yearly:
        return Subscription.TIER_STARTER
    elif price_id == pro_monthly or price_id == pro_yearly:
        return Subscription.TIER_PRO
    
    return None

