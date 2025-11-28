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

    name = models.CharField(max_length=255, db_index=True)
    description = models.TextField(blank=True)
    family = models.ForeignKey(Family, on_delete=models.CASCADE, related_name='tasks', db_index=True)
    assigned_to = models.ForeignKey(
        'a_family.User',
        on_delete=models.SET_NULL,
        related_name='tasks_assigned',
        null=True,
        blank=True,
        db_index=True,
    )
    created_by = models.ForeignKey('a_family.User', on_delete=models.CASCADE, related_name='tasks_created', db_index=True)
    completed = models.BooleanField(default=False, db_index=True)
    completed_by = models.ForeignKey(
        'a_family.User',
        on_delete=models.SET_NULL,
        related_name='tasks_completed',
        null=True,
        blank=True,
        db_index=True,
    )
    approved = models.BooleanField(default=False, db_index=True)
    approved_by = models.ForeignKey(
        'a_family.User',
        on_delete=models.SET_NULL,
        related_name='tasks_approved',
        null=True,
        blank=True,
        db_index=True,
    )
    due_date = models.DateField(null=True, blank=True, db_index=True)
    priority = models.IntegerField(default=PRIORITY_LOW, choices=PRIORITY_CHOICES, db_index=True)
    points = models.PositiveIntegerField(default=0)
    completed_at = models.DateTimeField(null=True, blank=True, db_index=True)
    approved_at = models.DateTimeField(null=True, blank=True)
    started_at = models.DateTimeField(null=True, blank=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'tasks_task'
        verbose_name = 'task'
        verbose_name_plural = 'tasks'
        ordering = ['-priority', 'due_date', 'name']
        indexes = [
            models.Index(fields=['family', 'completed']),
            models.Index(fields=['family', 'approved']),
            models.Index(fields=['assigned_to', 'completed']),
        ]

    @property
    def is_in_progress(self):
        """Check if task is currently in progress (started but not completed)"""
        return self.started_at is not None and not self.completed

    def __str__(self):
        return self.name
