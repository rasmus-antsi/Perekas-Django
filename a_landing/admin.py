from django.contrib import admin
from .models import ReviewFormSubmission


@admin.register(ReviewFormSubmission)
class ReviewFormSubmissionAdmin(admin.ModelAdmin):
    list_display = ['email', 'name', 'user', 'added_family_members', 'created_tasks', 'submitted_at']
    list_filter = ['added_family_members', 'created_tasks', 'created_rewards', 'created_shopping_lists', 'submitted_at']
    search_fields = ['email', 'name', 'why_created_account', 'what_prevented_usage', 'feedback']
    readonly_fields = ['submitted_at', 'ip_address']
    fieldsets = (
        ('Esitaja andmed', {
            'fields': ('user', 'email', 'name', 'submitted_at', 'ip_address')
        }),
        ('Küsimused', {
            'fields': ('why_created_account', 'added_family_members', 'created_tasks', 'created_rewards', 'created_shopping_lists')
        }),
        ('Tagasiside', {
            'fields': ('what_prevented_usage', 'feedback')
        }),
    )
    date_hierarchy = 'submitted_at'
