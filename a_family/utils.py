"""
Utility functions for family-related operations.
"""
from .models import Family


def get_family_for_user(user):
    """
    Get the first family for a user (as owner or member).
    
    Checks in this order:
    1. Families where user is a member (via ManyToMany relationship)
    2. Families where user is the owner
    
    Args:
        user: User instance
        
    Returns:
        Family instance or None if user has no associated family
    """
    if not user or not user.is_authenticated:
        return None
    
    try:
        # Try to get family where user is a member first (more common)
        # user.families is the reverse relation from Family.members ManyToManyField
        family = user.families.first()
        
        if family is None:
            # If not a member, check if user is owner
            family = Family.objects.filter(owner=user).first()
        
        return family
    except Exception:
        # Fallback: try owner lookup if reverse relation fails
        return Family.objects.filter(owner=user).first()

