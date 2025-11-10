from django.contrib.auth.models import User
from django.db import models

from a_family.models import Family


class Task(models.Model):
    PRIORITY_LOW = 0
    PRIORITY_MEDIUM = 1
    PRIORITY_HIGH = 2
    PRIORITY_CHOICES = [
        (PRIORITY_LOW, 'Low'),
        (PRIORITY_MEDIUM, 'Medium'),
        (PRIORITY_HIGH, 'High'),
    ]

    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    family = models.ForeignKey(Family, on_delete=models.CASCADE, related_name='tasks')
    assigned_to = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        related_name='tasks_assigned',
        null=True,
        blank=True,
    )
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='tasks_created')
    completed = models.BooleanField(default=False)
    completed_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        related_name='tasks_completed',
        null=True,
        blank=True,
    )
    approved = models.BooleanField(default=False)
    approved_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        related_name='tasks_approved',
        null=True,
        blank=True,
    )
    due_date = models.DateField(null=True, blank=True)
    priority = models.IntegerField(default=PRIORITY_LOW, choices=PRIORITY_CHOICES)
    points = models.PositiveIntegerField(default=0)
    completed_at = models.DateTimeField(null=True, blank=True)
    approved_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-priority', 'due_date', 'name']

    def __str__(self):
        return self.name
