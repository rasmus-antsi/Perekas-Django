from django.contrib.auth import get_user_model

User = get_user_model()
from django.utils import timezone
from datetime import date
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


def get_current_month_usage(family):
    """
    Get or create usage record for the current month.
    Returns the SubscriptionUsage object for the current month.
    """
    if not family:
        return None

    today = date.today()
    month_start = date(today.year, today.month, 1)

    usage, created = SubscriptionUsage.objects.get_or_create(
        family=family,
        month=month_start,
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

