from django.contrib import admin
from .models import Subscription, SubscriptionUsage


@admin.register(Subscription)
class SubscriptionAdmin(admin.ModelAdmin):
    list_display = ['owner', 'tier', 'status', 'current_period_start', 'current_period_end', 'created_at']
    list_filter = ['tier', 'status', 'created_at']
    search_fields = ['owner__username', 'owner__email', 'stripe_subscription_id', 'stripe_customer_id']
    readonly_fields = ['created_at', 'updated_at']
    fieldsets = (
        ('Owner', {
            'fields': ('owner',)
        }),
        ('Subscription Details', {
            'fields': ('tier', 'status', 'stripe_subscription_id', 'stripe_customer_id')
        }),
        ('Billing Period', {
            'fields': ('current_period_start', 'current_period_end')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at')
        }),
    )


@admin.register(SubscriptionUsage)
class SubscriptionUsageAdmin(admin.ModelAdmin):
    list_display = ['family', 'period_start', 'tasks_created', 'rewards_created', 'recurring_tasks_created', 'recurring_tasks_actual_count', 'updated_at']
    list_filter = ['period_start', 'updated_at']
    search_fields = ['family__name', 'family__owner__username']
    readonly_fields = ['updated_at', 'recurring_tasks_actual_count']
    date_hierarchy = 'period_start'
    
    fieldsets = (
        ('Family', {
            'fields': ('family',)
        }),
        ('Period', {
            'fields': ('period_start',)
        }),
        ('Usage Statistics', {
            'fields': ('tasks_created', 'rewards_created', 'recurring_tasks_created', 'recurring_tasks_actual_count')
        }),
        ('Timestamps', {
            'fields': ('updated_at',)
        }),
    )
    
    def recurring_tasks_actual_count(self, obj):
        """Display the actual count of recurring tasks for this family (read-only)"""
        from a_tasks.models import TaskRecurrence
        count = TaskRecurrence.objects.filter(task__family=obj.family).count()
        return count
    recurring_tasks_actual_count.short_description = 'Tegelik korduvate ülesannete arv'
