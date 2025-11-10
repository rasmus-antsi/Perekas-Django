from django.contrib import admin

from .models import Family, UserProfile


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "role", "points", "created_at", "updated_at")
    list_filter = ("role",)
    search_fields = ("user__username", "user__email", "user__first_name", "user__last_name")
    ordering = ("user__username",)
    readonly_fields = ("created_at", "updated_at")


@admin.register(Family)
class FamilyAdmin(admin.ModelAdmin):
    list_display = ("name", "owner", "id", "created_at", "updated_at")
    search_fields = ("name", "owner__username", "owner__email")
    filter_horizontal = ("members",)
    readonly_fields = ("created_at", "updated_at")