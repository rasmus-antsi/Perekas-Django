from random import randint

from django.contrib.auth.models import User
from django.db import models


class Family(models.Model):
    id = models.IntegerField(primary_key=True, default=randint(100000, 999999))
    owner = models.ForeignKey(User, on_delete=models.CASCADE)
    name = models.CharField(max_length=255)
    members = models.ManyToManyField(User, related_name='families')

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name

    def get_subscription(self):
        """Get subscription tier for this family via the owner"""
        from a_subscription.utils import get_family_subscription
        return get_family_subscription(self)

    def can_add_member(self, role):
        """Check if this family can add a member with the given role"""
        from a_subscription.utils import can_add_member
        return can_add_member(self, role)

    def has_shopping_list_access(self):
        """Check if this family has access to shopping list feature"""
        from a_subscription.utils import has_shopping_list_access
        return has_shopping_list_access(self)


class UserProfile(models.Model):
    ROLE_PARENT = 'parent'
    ROLE_CHILD = 'child'
    ROLE_CHOICES = [
        (ROLE_PARENT, 'Parent'),
        (ROLE_CHILD, 'Child'),
    ]

    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='family_profile',
    )
    role = models.CharField(max_length=12, choices=ROLE_CHOICES, default=ROLE_PARENT)
    points = models.PositiveIntegerField(default=0)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f'{self.user.get_full_name() or self.user.username} ({self.get_role_display()})'
