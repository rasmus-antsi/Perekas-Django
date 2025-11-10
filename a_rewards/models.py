from django.contrib.auth.models import User
from django.db import models

from a_family.models import Family


class Reward(models.Model):
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    points = models.PositiveIntegerField(default=0)
    family = models.ForeignKey(Family, related_name='rewards', on_delete=models.CASCADE)
    created_by = models.ForeignKey(User, related_name='rewards_created', on_delete=models.CASCADE)
    claimed = models.BooleanField(default=False)
    claimed_by = models.ForeignKey(
        User,
        related_name='rewards_claimed',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    claimed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['claimed', '-created_at', 'name']

    def __str__(self):
        return self.name