from django.contrib import admin

from .models import Reward


@admin.register(Reward)
class RewardAdmin(admin.ModelAdmin):
    list_display = ('name', 'family', 'points', 'created_by', 'claimed', 'claimed_by', 'claimed_at', 'created_at')
    list_filter = ('family', 'claimed', 'created_by', 'claimed_by', 'points', 'created_at', 'claimed_at')
    search_fields = ('name', 'description', 'family__name', 'created_by__username', 'created_by__email', 'claimed_by__username', 'claimed_by__email')
    readonly_fields = ('created_at', 'updated_at', 'claimed_at')
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'description', 'family', 'points', 'created_by')
        }),
        ('Claim Status', {
            'fields': ('claimed', 'claimed_by', 'claimed_at')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at')
        }),
    )
    date_hierarchy = 'created_at'
    ordering = ('-created_at',)
