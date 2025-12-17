from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib import messages

from .models import Family, User, EmailTemplate
from .emails import send_bulk_email


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ('username', 'email', 'first_name', 'last_name', 'role', 'birthdate', 'points', 'is_staff', 'date_joined')
    list_filter = ('role', 'is_staff', 'is_superuser', 'is_active', 'date_joined', 'birthdate')
    fieldsets = BaseUserAdmin.fieldsets + (
        ('Perekas Profile', {'fields': ('role', 'birthdate', 'points')}),
    )
    add_fieldsets = BaseUserAdmin.add_fieldsets + (
        ('Perekas Profile', {'fields': ('role', 'birthdate', 'points')}),
    )


@admin.register(Family)
class FamilyAdmin(admin.ModelAdmin):
    list_display = ('name', 'owner', 'id', 'created_at', 'updated_at')
    list_filter = ('created_at',)
    search_fields = ('name', 'owner__username', 'owner__email')
    filter_horizontal = ('members',)
    readonly_fields = ('id', 'created_at', 'updated_at')


@admin.register(EmailTemplate)
class EmailTemplateAdmin(admin.ModelAdmin):
    list_display = ('name', 'subject', 'is_active', 'updated_at', 'created_at')
    list_filter = ('is_active', 'created_at', 'updated_at')
    search_fields = ('name', 'subject', 'body_html')
    readonly_fields = ('created_at', 'updated_at')
    actions = ['send_to_all_users', 'send_to_parents', 'send_to_children']
    
    fieldsets = (
        (None, {
            'fields': ('name', 'subject', 'is_active')
        }),
        ('Content', {
            'fields': ('body_html',),
            'description': 'HTML content for the email body. Use inline styles for best email client compatibility.'
        }),
        ('Metadata', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    @admin.action(description="Send email to ALL users with email")
    def send_to_all_users(self, request, queryset):
        if queryset.count() != 1:
            self.message_user(request, "Please select exactly one template to send.", messages.ERROR)
            return
        
        template = queryset.first()
        if not template.is_active:
            self.message_user(request, f"Template '{template.name}' is not active.", messages.ERROR)
            return
        
        users = User.objects.filter(email__isnull=False).exclude(email='')
        sent, skipped = send_bulk_email(template, users)
        self.message_user(
            request, 
            f"Email '{template.subject}' sent to {sent} users ({skipped} skipped - no email).",
            messages.SUCCESS
        )
    
    @admin.action(description="Send email to PARENTS only")
    def send_to_parents(self, request, queryset):
        if queryset.count() != 1:
            self.message_user(request, "Please select exactly one template to send.", messages.ERROR)
            return
        
        template = queryset.first()
        if not template.is_active:
            self.message_user(request, f"Template '{template.name}' is not active.", messages.ERROR)
            return
        
        users = User.objects.filter(role=User.ROLE_PARENT, email__isnull=False).exclude(email='')
        sent, skipped = send_bulk_email(template, users)
        self.message_user(
            request, 
            f"Email '{template.subject}' sent to {sent} parents ({skipped} skipped - no email).",
            messages.SUCCESS
        )
    
    @admin.action(description="Send email to CHILDREN only")
    def send_to_children(self, request, queryset):
        if queryset.count() != 1:
            self.message_user(request, "Please select exactly one template to send.", messages.ERROR)
            return
        
        template = queryset.first()
        if not template.is_active:
            self.message_user(request, f"Template '{template.name}' is not active.", messages.ERROR)
            return
        
        users = User.objects.filter(role=User.ROLE_CHILD, email__isnull=False).exclude(email='')
        sent, skipped = send_bulk_email(template, users)
        self.message_user(
            request, 
            f"Email '{template.subject}' sent to {sent} children ({skipped} skipped - no email).",
            messages.SUCCESS
        )