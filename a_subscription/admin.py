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
    list_display = ['family', 'month', 'tasks_created', 'rewards_created', 'updated_at']
    list_filter = ['month', 'updated_at']
    search_fields = ['family__name', 'family__owner__username']
    readonly_fields = ['updated_at']
    date_hierarchy = 'month'
