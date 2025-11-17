import uuid

from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    ROLE_PARENT = 'parent'
    ROLE_CHILD = 'child'
    ROLE_CHOICES = [
        (ROLE_PARENT, 'Parent'),
        (ROLE_CHILD, 'Child'),
    ]

    role = models.CharField(max_length=12, choices=ROLE_CHOICES, default=ROLE_PARENT, db_index=True)
    points = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'auth_user'
        verbose_name = 'user'
        verbose_name_plural = 'users'

    def __str__(self):
        return f'{self.get_full_name() or self.username} ({self.get_role_display()})'


class Family(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner = models.ForeignKey('User', on_delete=models.CASCADE, db_index=True)
    name = models.CharField(max_length=255, db_index=True)
    members = models.ManyToManyField('User', related_name='families')

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'family_family'
        verbose_name = 'family'
        verbose_name_plural = 'families'
        ordering = ['-created_at']

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
