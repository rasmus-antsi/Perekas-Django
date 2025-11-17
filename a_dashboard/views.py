from django.contrib.auth.decorators import login_required
from django.db.models import Count, Sum, Q
from django.shortcuts import render
from django.utils import timezone

from a_family.models import Family, UserProfile
from a_rewards.models import Reward
from a_shopping.models import ShoppingListItem
from a_tasks.models import Task


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

    profile = getattr(user, "family_profile", None)
    if profile is None and family and family.owner_id == user.id:
        profile, _ = UserProfile.objects.get_or_create(user=user, defaults={"role": UserProfile.ROLE_PARENT})

    is_parent = profile and profile.role == UserProfile.ROLE_PARENT
    is_child = profile and profile.role == UserProfile.ROLE_CHILD

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
            "label": "Manage Tasks",
            "description": "Create and assign family tasks",
            "url": "a_tasks:index",
            "icon": "tasks",
        },
        {
            "label": "View Rewards",
            "description": "Claim rewards with earned points",
            "url": "a_rewards:index",
            "icon": "trophy",
        },
        {
            "label": "Shopping List",
            "description": "Manage family shopping items",
            "url": "a_shopping:index",
            "icon": "cart",
        },
    ]

    if family:
        tasks_qs = Task.objects.filter(family=family)
        stats["active_tasks"] = tasks_qs.filter(completed=False).count()

        week_ago = timezone.now() - timezone.timedelta(days=7)
        stats["tasks_change"] = tasks_qs.filter(created_at__gte=week_ago).count()

        child_profiles = UserProfile.objects.filter(user__in=family.members.all(), role=UserProfile.ROLE_CHILD)
        stats["points_earned"] = child_profiles.aggregate(total=Sum("points"))["total"] or 0

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
            member_profile, _ = UserProfile.objects.get_or_create(user=member)
            total_tasks = tasks_qs.filter(assigned_to=member).count()
            total_tasks_display = total_tasks if total_tasks else stats["active_tasks"] or tasks_qs.count()
            completed_count = tasks_qs.filter(
                completed=True,
                approved=True,
                completed_by=member,
            ).count()
            progress_ratio = completed_count / total_tasks_display if total_tasks_display else 0

            display_name = member.get_full_name() or member.username
            family_members.append(
                {
                    "name": display_name,
                    "initials": display_name[:2].upper(),
                    "points": member_profile.points,
                    "tasks_completed": completed_count,
                    "progress": int(progress_ratio * 100),
                    "role": member_profile.get_role_display(),
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
        "profile": profile,
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
    user = request.user
    family = _get_family_for_user(user)

    profile = getattr(user, "family_profile", None)
    if profile is None and family and family.owner_id == user.id:
        profile, _ = UserProfile.objects.get_or_create(user=user, defaults={"role": UserProfile.ROLE_PARENT})

    is_parent = profile and profile.role == UserProfile.ROLE_PARENT
    is_child = profile and profile.role == UserProfile.ROLE_CHILD
    settings_user = profile.user if profile else user
    current_role = profile.role if profile else None

    notification_preferences = {
        "task_updates": True,
        "reward_updates": True,
        "shopping_updates": False,
        "weekly_summary": True,
    }

    context = {
        "family": family,
        "profile": profile,
        "is_parent": is_parent,
        "is_child": is_child,
        "settings_user": settings_user,
        "role_parent": UserProfile.ROLE_PARENT,
        "role_child": UserProfile.ROLE_CHILD,
        "current_role": current_role,
        "notification_preferences": notification_preferences,
    }
    return render(request, 'a_dashboard/settings.html', context)