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
    quick_actions_parent = [
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
    quick_actions_child = [
        {
            "label": "Minu ülesanded",
            "description": "Vaata ja märgi oma töid",
            "url": "a_tasks:index",
            "icon": "tasks",
        },
        {
            "label": "Preemiad",
            "description": "Vali siht ja lunasta",
            "url": "a_rewards:index",
            "icon": "trophy",
        },
    ]
    
    # Add shopping list action if subscription allows it
    if family and has_shopping_list_access(family):
        quick_actions_parent.append({
            "label": "Ostunimekiri",
            "description": "Halda pere sisseoste ja vajalikke tooteid",
            "url": "a_shopping:index",
            "icon": "cart",
        })
        quick_actions_child.append({
            "label": "Ostunimekiri",
            "description": "Lisa asju, mida vajad",
            "url": "a_shopping:index",
            "icon": "cart",
        })

    role_view = 'parent' if is_parent else 'child'
    child_context = None

    parent_stat_cards = []

    if family:
        today = timezone.localdate()
        now = timezone.now()
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

        if is_parent:
            pending_approvals_count = tasks_qs.filter(completed=True, approved=False).count()
            due_today_count = tasks_qs.filter(completed=False, due_date=today).count()
            weekly_points = tasks_qs.filter(
                approved=True,
                approved_at__gte=now - timezone.timedelta(days=7)
            ).aggregate(total=Sum("points"))["total"] or 0
            claimable_now = rewards_qs.filter(claimed=False, points__lte=child_users.aggregate(total=Sum("points"))["total"] or 0).count()
            parent_stat_cards = [
                {
                    "label": "Aktiivsed ülesanded",
                    "value": stats["active_tasks"],
                    "change": f"{pending_approvals_count} ootab kinnitamist",
                    "icon": "icon-purple",
                    "url": "a_tasks:index",
                },
                {
                    "label": "Tänased tähtajad",
                    "value": due_today_count,
                    "change": "Vaata ja planeri päev",
                    "icon": "icon-green",
                    "url": "a_tasks:index",
                },
                {
                    "label": "Punktid sel nädalal",
                    "value": weekly_points,
                    "change": f"{stats['points_earned']} kokku lastel",
                    "icon": "icon-orange",
                    "url": "a_rewards:index",
                },
                {
                    "label": "Ostunimekiri",
                    "value": stats["shopping_needed"],
                    "change": f"{stats['shopping_items'] - stats['shopping_needed']} korvis",
                    "icon": "icon-teal",
                    "url": "a_shopping:index" if has_shopping_list_access(family) else "a_tasks:index",
                },
            ]

        if is_child:
            today = timezone.localdate()
            # Include tasks assigned to this user OR assigned to all (None)
            child_tasks = tasks_qs.filter(
                Q(assigned_to=user) | Q(assigned_to__isnull=True)
            ).filter(completed=False)
            # Today's tasks: due today, overdue (past), or no due date
            today_tasks = list(
                child_tasks.filter(
                    Q(due_date__lte=today) | Q(due_date__isnull=True)
                ).order_by("-priority", "due_date")[:5]
            )
            upcoming_tasks = list(
                child_tasks.filter(due_date__gt=today)
                .order_by("due_date")[:5]
            )
            pending_reviews = list(
                tasks_qs.filter(completed=True, approved=False, completed_by=user)
                .order_by("-completed_at")[:4]
            )
            recent_child_activity = list(
                tasks_qs.filter(completed_by=user)
                .order_by("-completed_at")[:5]
            )
            rewards_qs = list(
                Reward.objects.filter(family=family, claimed=False)
                .order_by("points")[:4]
            )
            next_reward = None
            for reward in rewards_qs:
                if reward.points > user.points:
                    next_reward = reward
                    break
            weekly_points = tasks_qs.filter(
                completed_by=user,
                approved=True,
                approved_at__gte=timezone.now() - timezone.timedelta(days=7)
            ).aggregate(total=Sum("points"))["total"] or 0
            rewards_available = []
            for reward in rewards_qs:
                rewards_available.append({
                    "id": reward.id,
                    "name": reward.name,
                    "points": reward.points,
                    "is_goal": next_reward and reward.id == next_reward.id,
                    "available_now": reward.points <= user.points,
                    "shortfall": max(reward.points - user.points, 0),
                })

            child_context = {
                "today_tasks": today_tasks,
                "upcoming_tasks": upcoming_tasks,
                "pending_reviews": pending_reviews,
                "recent_activity": recent_child_activity,
                "rewards_available": rewards_available,
                "next_reward": next_reward,
                "points_total": user.points,
                "points_week": weekly_points,
                "points_needed": (next_reward.points - user.points) if next_reward else 0,
                "quick_actions": quick_actions_child,
            }

    context = {
        "family": family,
        "is_parent": is_parent,
        "is_child": is_child,
        "stats": stats,
        "family_members": family_members,
        "recent_tasks": recent_tasks,
        "quick_actions": quick_actions_parent,
        "parent_stat_cards": parent_stat_cards,
        "role_view": role_view,
        "child_context": child_context,
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