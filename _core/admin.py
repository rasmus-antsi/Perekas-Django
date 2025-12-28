"""
Custom Django Admin configuration with dashboard.
"""
from django.contrib import admin
from django.contrib.admin.views.decorators import staff_member_required
from django.utils.decorators import method_decorator
from django.views.generic import TemplateView
from django.db.models import Count, Q, Avg, Sum
from django.utils import timezone
from datetime import timedelta

from a_family.models import User, Family
from a_tasks.models import Task, TaskRecurrence
from a_rewards.models import Reward
from a_subscription.models import Subscription


@method_decorator(staff_member_required, name='dispatch')
class AdminDashboardView(TemplateView):
    """Custom admin dashboard view with statistics."""
    template_name = 'admin/dashboard.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        now = timezone.now()
        
        # Time periods
        days_7_ago = now - timedelta(days=7)
        days_30_ago = now - timedelta(days=30)
        days_90_ago = now - timedelta(days=90)

        # ========== USER STATISTICS ==========
        total_users = User.objects.count()
        total_parents = User.objects.filter(role=User.ROLE_PARENT).count()
        total_children = User.objects.filter(role=User.ROLE_CHILD).count()
        
        new_users_7d = User.objects.filter(date_joined__gte=days_7_ago).count()
        new_users_30d = User.objects.filter(date_joined__gte=days_30_ago).count()
        new_users_90d = User.objects.filter(date_joined__gte=days_90_ago).count()
        
        # Active users (logged in within period)
        active_users_7d = User.objects.filter(last_login__gte=days_7_ago).count()
        active_users_30d = User.objects.filter(last_login__gte=days_30_ago).count()
        
        # Users by role
        users_by_role = {
            'parents': total_parents,
            'children': total_children,
        }

        # ========== FAMILY STATISTICS ==========
        total_families = Family.objects.count()
        new_families_7d = Family.objects.filter(created_at__gte=days_7_ago).count()
        new_families_30d = Family.objects.filter(created_at__gte=days_30_ago).count()
        new_families_90d = Family.objects.filter(created_at__gte=days_90_ago).count()
        
        # Average family size (owner + members)
        families_with_sizes = Family.objects.annotate(
            size=Count('members') + 1  # +1 for owner
        )
        avg_family_size = families_with_sizes.aggregate(Avg('size'))['size__avg'] or 0

        # ========== TASK STATISTICS ==========
        total_tasks = Task.objects.count()
        completed_tasks = Task.objects.filter(completed=True).count()
        completion_rate = (completed_tasks / total_tasks * 100) if total_tasks > 0 else 0
        
        # Tasks by priority
        tasks_by_priority = {
            'low': Task.objects.filter(priority=Task.PRIORITY_LOW).count(),
            'medium': Task.objects.filter(priority=Task.PRIORITY_MEDIUM).count(),
            'high': Task.objects.filter(priority=Task.PRIORITY_HIGH).count(),
        }
        
        # Tasks created in time periods
        tasks_created_7d = Task.objects.filter(created_at__gte=days_7_ago).count()
        tasks_created_30d = Task.objects.filter(created_at__gte=days_30_ago).count()
        
        # Tasks completed in time periods
        tasks_completed_7d = Task.objects.filter(completed=True, completed_at__gte=days_7_ago).count()
        tasks_completed_30d = Task.objects.filter(completed=True, completed_at__gte=days_30_ago).count()
        
        # Average tasks per family
        families_with_task_counts = Family.objects.annotate(
            task_count=Count('tasks')
        )
        avg_tasks_per_family = families_with_task_counts.aggregate(Avg('task_count'))['task_count__avg'] or 0
        
        # Recurring tasks count
        recurring_tasks_count = TaskRecurrence.objects.count()

        # ========== REWARD STATISTICS ==========
        total_rewards = Reward.objects.count()
        claimed_rewards = Reward.objects.filter(claimed=True).count()
        claim_rate = (claimed_rewards / total_rewards * 100) if total_rewards > 0 else 0
        
        # Rewards created in time periods
        rewards_created_7d = Reward.objects.filter(created_at__gte=days_7_ago).count()
        rewards_created_30d = Reward.objects.filter(created_at__gte=days_30_ago).count()
        
        # Rewards claimed in time periods
        rewards_claimed_7d = Reward.objects.filter(claimed=True, claimed_at__gte=days_7_ago).count()
        rewards_claimed_30d = Reward.objects.filter(claimed=True, claimed_at__gte=days_30_ago).count()

        # ========== SUBSCRIPTION STATISTICS ==========
        total_subscriptions = Subscription.objects.count()
        
        # Subscriptions by tier
        subscriptions_by_tier = {
            'FREE': Subscription.objects.filter(tier=Subscription.TIER_FREE).count(),
            'STARTER': Subscription.objects.filter(tier=Subscription.TIER_STARTER).count(),
            'PRO': Subscription.objects.filter(tier=Subscription.TIER_PRO).count(),
        }
        
        # Active subscriptions (active or trialing status)
        active_subscriptions = Subscription.objects.filter(
            Q(status=Subscription.STATUS_ACTIVE) | Q(status=Subscription.STATUS_TRIALING)
        ).count()
        
        # Subscription status breakdown
        status_breakdown = {}
        for status_code, status_label in Subscription.STATUS_CHOICES:
            status_breakdown[status_label] = Subscription.objects.filter(status=status_code).count()

        # ========== ENGAGEMENT METRICS ==========
        # Most active families (by task completion)
        most_active_families = Family.objects.annotate(
            completed_task_count=Count('tasks', filter=Q(tasks__completed=True))
        ).order_by('-completed_task_count')[:10]
        
        # Average points per user
        avg_points_per_user = User.objects.aggregate(Avg('points'))['points__avg'] or 0

        # ========== OVERVIEW CARDS ==========
        context.update({
            # Overview cards
            'total_users': total_users,
            'total_families': total_families,
            'active_subscriptions': active_subscriptions,
            'tasks_completed_30d': tasks_completed_30d,
            
            # User statistics
            'total_parents': total_parents,
            'total_children': total_children,
            'new_users_7d': new_users_7d,
            'new_users_30d': new_users_30d,
            'new_users_90d': new_users_90d,
            'active_users_7d': active_users_7d,
            'active_users_30d': active_users_30d,
            'users_by_role': users_by_role,
            
            # Family statistics
            'new_families_7d': new_families_7d,
            'new_families_30d': new_families_30d,
            'new_families_90d': new_families_90d,
            'avg_family_size': round(avg_family_size, 2),
            
            # Task statistics
            'total_tasks': total_tasks,
            'completed_tasks': completed_tasks,
            'completion_rate': round(completion_rate, 1),
            'tasks_by_priority': tasks_by_priority,
            'tasks_created_7d': tasks_created_7d,
            'tasks_created_30d': tasks_created_30d,
            'tasks_completed_7d': tasks_completed_7d,
            'tasks_completed_30d': tasks_completed_30d,
            'avg_tasks_per_family': round(avg_tasks_per_family, 2),
            'recurring_tasks_count': recurring_tasks_count,
            
            # Reward statistics
            'total_rewards': total_rewards,
            'claimed_rewards': claimed_rewards,
            'claim_rate': round(claim_rate, 1),
            'rewards_created_7d': rewards_created_7d,
            'rewards_created_30d': rewards_created_30d,
            'rewards_claimed_7d': rewards_claimed_7d,
            'rewards_claimed_30d': rewards_claimed_30d,
            
            # Subscription statistics
            'total_subscriptions': total_subscriptions,
            'subscriptions_by_tier': subscriptions_by_tier,
            'status_breakdown': status_breakdown,
            
            # Engagement metrics
            'most_active_families': most_active_families,
            'avg_points_per_user': round(avg_points_per_user, 1),
        })
        
        return context


class CustomAdminSite(admin.AdminSite):
    """Custom admin site with dashboard."""
    site_header = 'Perekas Admin'
    site_title = 'Perekas Admin'
    index_title = 'Dashboard'

    def get_urls(self):
        """Add dashboard URL to admin URLs."""
        from django.urls import path
        urls = super().get_urls()
        custom_urls = [
            path('dashboard/', self.admin_view(AdminDashboardView.as_view()), name='admin_dashboard'),
        ]
        return custom_urls + urls

    def index(self, request, extra_context=None):
        """Override index to redirect to dashboard."""
        from django.shortcuts import redirect
        return redirect('admin:admin_dashboard')


# Create custom admin site instance
admin_site = CustomAdminSite(name='admin')

# Import all admin modules to ensure models are registered with default admin.site first
# This must happen after creating admin_site but before it's used
def _register_all_models():
    """Register all models with the custom admin site."""
    # Import all admin modules (this triggers @admin.register decorators with default admin.site)
    from a_family import admin as family_admin
    from a_tasks import admin as tasks_admin
    from a_rewards import admin as rewards_admin
    from a_subscription import admin as subscription_admin
    from a_shopping import admin as shopping_admin
    
    # Copy all registrations from default admin.site to custom site
    # We need to re-register with the admin class, not the instance
    for model, admin_instance in admin.site._registry.items():
        if model not in admin_site._registry:
            # Get the admin class from the instance
            admin_class = admin_instance.__class__
            # Re-register with custom site
            admin_site.register(model, admin_class)

# Call this function to set up registrations
# Note: This will be called when the module is imported
_register_all_models()
