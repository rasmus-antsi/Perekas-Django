from django.contrib import admin

from .models import ShoppingListItem


@admin.register(ShoppingListItem)
class ShoppingListItemAdmin(admin.ModelAdmin):
    list_display = ('name', 'family', 'added_by', 'in_cart', 'created_at', 'updated_at')
    list_filter = ('family', 'in_cart', 'added_by', 'created_at')
    search_fields = ('name', 'family__name', 'added_by__username', 'added_by__email')
    readonly_fields = ('created_at', 'updated_at')
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'family', 'added_by', 'in_cart')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at')
        }),
    )
    date_hierarchy = 'created_at'
    ordering = ('-created_at',)
