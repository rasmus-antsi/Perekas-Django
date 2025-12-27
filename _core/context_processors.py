"""
Context processors to provide common data to all templates
"""
from django.conf import settings

from a_subscription.utils import get_family_subscription, has_shopping_list_access


def debug_context(request):
    """Add DEBUG setting and META_PIXEL_ID to template context"""
    return {
        'DEBUG': settings.DEBUG,
        'META_PIXEL_ID': getattr(settings, 'META_PIXEL_ID', '1709109120064941'),
    }


def subscription_context(request):
    """Add subscription and shopping list access info to all templates"""
    if not request.user.is_authenticated:
        return {
            'has_shopping_list_access': False,
            'user_subscription_tier': 'FREE',
        }
    
    # Get user's family
    family = None
    if hasattr(request.user, "families"):
        family = request.user.families.first()
    if family is None:
        from a_family.models import Family
        family = Family.objects.filter(owner=request.user).first()
    
    # Get subscription tier
    tier = get_family_subscription(family) if family else 'FREE'
    
    # Check shopping list access (for all users if subscription allows it)
    shopping_access = False
    if family:
        shopping_access = has_shopping_list_access(family)
    
    return {
        'has_shopping_list_access': shopping_access,
        'user_subscription_tier': tier,
        'user_family': family,
    }

