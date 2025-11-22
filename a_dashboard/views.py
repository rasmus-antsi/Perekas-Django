import logging
import stripe
from datetime import datetime
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Sum, Q
from django.shortcuts import redirect, render
from django.utils import timezone
from django.conf import settings as django_settings

logger = logging.getLogger(__name__)

from a_family.models import Family, User
from a_rewards.models import Reward
from a_shopping.models import ShoppingListItem
from a_tasks.models import Task
from a_subscription.models import Subscription
from a_subscription.utils import (
    get_family_subscription,
    get_current_month_usage,
    get_tier_limits,
    has_shopping_list_access,
)


def _get_family_for_user(user):
    family = None
    if hasattr(user, "families"):
        family = user.families.first()
    if family is None:
        family = Family.objects.filter(owner=user).first()
    return family


@login_required
def dashboard(request):
    user = request.user
    family = _get_family_for_user(user)

    # Redirect to onboarding if user doesn't have a family
    if not family:
        return redirect('a_family:onboarding')

    # Set default role for owner if not set
    if family and family.owner_id == user.id and not user.role:
        user.role = User.ROLE_PARENT
        user.save(update_fields=['role'])

    is_parent = user.role == User.ROLE_PARENT
    is_child = user.role == User.ROLE_CHILD

    stats = {
        "active_tasks": 0,
        "tasks_change": 0,
        "points_earned": 0,
        "points_change": 0,
        "rewards_available": 0,
        "rewards_change": 0,
        "shopping_items": 0,
        "shopping_needed": 0,
    }
    family_members = []
    recent_tasks = []
    quick_actions = [
        {
            "label": "Halda ülesandeid",
            "description": "Loo ja määra perele uued ülesanded",
            "url": "a_tasks:index",
            "icon": "tasks",
        },
        {
            "label": "Vaata preemiaid",
            "description": "Kasuta kogutud punkte ihatud preemiateks",
            "url": "a_rewards:index",
            "icon": "trophy",
        },
    ]
    
    # Add shopping list action for all users if subscription allows it
    if family and has_shopping_list_access(family):
        quick_actions.append({
            "label": "Ostunimekiri",
            "description": "Halda pere sisseoste ja vajalikke tooteid",
            "url": "a_shopping:index",
            "icon": "cart",
        })

    if family:
        tasks_qs = Task.objects.filter(family=family)
        stats["active_tasks"] = tasks_qs.filter(completed=False).count()

        week_ago = timezone.now() - timezone.timedelta(days=7)
        stats["tasks_change"] = tasks_qs.filter(created_at__gte=week_ago).count()

        child_users = family.members.filter(role=User.ROLE_CHILD)
        stats["points_earned"] = child_users.aggregate(total=Sum("points"))["total"] or 0

        month_ago = timezone.now() - timezone.timedelta(days=30)
        recent_task_points = (
            Task.objects.filter(family=family, approved=True, approved_at__gte=month_ago)
            .aggregate(total=Sum("points"))
            .get("total")
        )
        stats["points_change"] = recent_task_points or 0

        rewards_qs = Reward.objects.filter(family=family)
        stats["rewards_available"] = rewards_qs.filter(claimed=False).count()
        stats["rewards_change"] = rewards_qs.filter(claimed=False, created_at__gte=week_ago).count()

        shopping_qs = ShoppingListItem.objects.filter(family=family)
        stats["shopping_items"] = shopping_qs.count()
        stats["shopping_needed"] = shopping_qs.filter(in_cart=False).count()

        members = list(family.members.all())
        if family.owner_id not in [member.id for member in members]:
            members.append(family.owner)

        for member in members:
            total_tasks = tasks_qs.filter(assigned_to=member).count()
            total_tasks_display = total_tasks if total_tasks else stats["active_tasks"] or tasks_qs.count()
            completed_count = tasks_qs.filter(
                completed=True,
                approved=True,
                completed_by=member,
            ).count()
            progress_ratio = completed_count / total_tasks_display if total_tasks_display else 0

            display_name = member.get_display_name()
            family_members.append(
                {
                    "name": display_name,
                    "initials": display_name[:2].upper(),
                    "points": member.points,
                    "tasks_completed": completed_count,
                    "progress": int(progress_ratio * 100),
                    "role": member.get_role_display(),
                    "total_tasks": total_tasks_display,
                }
            )

        recent_tasks = list(
            tasks_qs.filter(completed=True)
            .select_related("completed_by")
            .order_by("-completed_at")[:5]
        )

    context = {
        "family": family,
        "is_parent": is_parent,
        "is_child": is_child,
        "stats": stats,
        "family_members": family_members,
        "recent_tasks": recent_tasks,
        "quick_actions": quick_actions,
    }
    return render(request, 'a_dashboard/dashboard.html', context)


@login_required
def settings(request):
    """Redirect old dashboard settings to new account settings page"""
    from django.urls import reverse
    
    # Get section from query params if present
    section = request.GET.get('section', 'general')
    if section not in ['general', 'notifications', 'subscriptions']:
        section = 'general'
    
    # Redirect to new settings page with same section
    return redirect(f"{reverse('a_account:settings')}?section={section}")