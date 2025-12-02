from django.contrib import admin

from .models import Task, TaskRecurrence


class TaskRecurrenceInline(admin.TabularInline):
    model = TaskRecurrence
    extra = 0
    fields = ('frequency', 'day_of_week', 'day_of_month', 'end_date', 'next_occurrence', 'created_at')
    readonly_fields = ('created_at',)
    can_delete = True


@admin.register(Task)
class TaskAdmin(admin.ModelAdmin):
    list_display = ('name', 'family', 'assigned_to', 'created_by', 'priority', 'points', 'completed', 'approved', 'has_recurrence', 'due_date', 'created_at')
    list_filter = ('family', 'priority', 'completed', 'approved', 'created_by', 'assigned_to', 'due_date', 'created_at', 'recurrences')
    search_fields = ('name', 'description', 'family__name', 'assigned_to__username', 'assigned_to__email', 'created_by__username', 'created_by__email')
    readonly_fields = ('created_at', 'updated_at', 'completed_at', 'approved_at')
    inlines = [TaskRecurrenceInline]
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

    def has_recurrence(self, obj):
        """Check if task has a recurrence"""
        return obj.recurrences.exists()
    has_recurrence.boolean = True
    has_recurrence.short_description = 'Recurring'


@admin.register(TaskRecurrence)
class TaskRecurrenceAdmin(admin.ModelAdmin):
    list_display = ('task', 'frequency', 'day_of_week', 'day_of_month', 'end_date', 'next_occurrence', 'created_at')
    list_filter = ('frequency', 'end_date', 'next_occurrence', 'created_at')
    search_fields = ('task__name', 'task__family__name')
    readonly_fields = ('created_at',)
    fieldsets = (
        ('Recurrence Information', {
            'fields': ('task', 'frequency', 'interval', 'day_of_week', 'day_of_month', 'end_date', 'next_occurrence')
        }),
        ('Timestamps', {
            'fields': ('created_at',)
        }),
    )
    date_hierarchy = 'next_occurrence'
    ordering = ('next_occurrence',)
