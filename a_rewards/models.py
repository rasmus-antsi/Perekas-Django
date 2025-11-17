from django.db import models

from a_family.models import Family


class Reward(models.Model):
    name = models.CharField(max_length=255, db_index=True)
    description = models.TextField(blank=True)
    points = models.PositiveIntegerField(default=0, db_index=True)
    family = models.ForeignKey(Family, related_name='rewards', on_delete=models.CASCADE, db_index=True)
    created_by = models.ForeignKey('a_family.User', related_name='rewards_created', on_delete=models.CASCADE, db_index=True)
    claimed = models.BooleanField(default=False, db_index=True)
    claimed_by = models.ForeignKey(
        'a_family.User',
        related_name='rewards_claimed',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        db_index=True,
    )
    claimed_at = models.DateTimeField(null=True, blank=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'rewards_reward'
        verbose_name = 'reward'
        verbose_name_plural = 'rewards'
        ordering = ['claimed', '-created_at', 'name']
        indexes = [
            models.Index(fields=['family', 'claimed']),
            models.Index(fields=['family', 'points']),
        ]

    def __str__(self):
        return self.name