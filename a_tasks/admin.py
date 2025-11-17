from django.contrib import admin

from .models import Task


@admin.register(Task)
class TaskAdmin(admin.ModelAdmin):
    list_display = ('name', 'family', 'assigned_to', 'created_by', 'priority', 'points', 'completed', 'approved', 'due_date', 'created_at')
    list_filter = ('family', 'priority', 'completed', 'approved', 'created_by', 'assigned_to', 'due_date', 'created_at')
    search_fields = ('name', 'description', 'family__name', 'assigned_to__username', 'assigned_to__email', 'created_by__username', 'created_by__email')
    readonly_fields = ('created_at', 'updated_at', 'completed_at', 'approved_at')
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'description', 'family', 'priority', 'points', 'due_date')
        }),
        ('Assignment', {
            'fields': ('assigned_to', 'created_by')
        }),
        ('Status', {
            'fields': ('completed', 'completed_by', 'completed_at', 'approved', 'approved_by', 'approved_at')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at')
        }),
    )
    date_hierarchy = 'created_at'
    ordering = ('-created_at',)
