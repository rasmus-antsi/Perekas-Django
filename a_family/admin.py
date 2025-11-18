from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import Family, User


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ('username', 'email', 'first_name', 'last_name', 'role', 'points', 'is_staff', 'date_joined')
    list_filter = ('role', 'is_staff', 'is_superuser', 'is_active', 'date_joined')
    fieldsets = BaseUserAdmin.fieldsets + (
        ('Perekas Profile', {'fields': ('role', 'points')}),
    )
    add_fieldsets = BaseUserAdmin.add_fieldsets + (
        ('Perekas Profile', {'fields': ('role', 'points')}),
    )


@admin.register(Family)
class FamilyAdmin(admin.ModelAdmin):
    list_display = ('name', 'owner', 'id', 'created_at', 'updated_at')
    list_filter = ('created_at',)
    search_fields = ('name', 'owner__username', 'owner__email')
    filter_horizontal = ('members',)
    readonly_fields = ('id', 'created_at', 'updated_at')