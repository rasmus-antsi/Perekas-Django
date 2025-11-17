import itertools

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.utils import timezone

from a_family.models import Family, UserProfile
from a_subscription.utils import check_subscription_limit, increment_usage

from .models import Reward


def _get_family_for_user(user):
    family = None
    if hasattr(user, "families"):
        family = user.families.first()
    if family is None:
        family = Family.objects.filter(owner=user).first()
    return family


def _get_or_create_profile(user, default_role=UserProfile.ROLE_CHILD):
    if user is None:
        return None
    profile, _ = UserProfile.objects.get_or_create(
        user=user,
        defaults={"role": default_role},
    )
    return profile


@login_required
def index(request):
    user = request.user
    family = _get_family_for_user(user)

    profile = getattr(user, "family_profile", None)
    if profile is None and family and family.owner_id == user.id:
        profile = _get_or_create_profile(user, default_role=UserProfile.ROLE_PARENT)

    role = profile.role if profile else (UserProfile.ROLE_PARENT if family and family.owner_id == user.id else None)
    is_parent = role == UserProfile.ROLE_PARENT
    is_child = role == UserProfile.ROLE_CHILD

    if request.method == "POST" and family:
        action = request.POST.get("action")
        reward_id = request.POST.get("reward_id")

        def _get_reward():
            if not reward_id:
                return None
            return Reward.objects.filter(family=family, id=reward_id).select_related("claimed_by__family_profile").first()

        if action == "create" and is_parent:
            name = request.POST.get("name", "").strip()
            description = request.POST.get("description", "").strip()
            points_raw = request.POST.get("points", "0")

            if name:
                # Check subscription limit before creating
                can_create, current_count, limit, tier = check_subscription_limit(family, 'rewards', 1)
                if not can_create:
                    messages.error(
                        request,
                        f"You've reached your monthly reward limit ({limit} rewards). "
                        f"You've created {current_count} rewards this month. "
                        f"Please upgrade your subscription to create more rewards."
                    )
                    return redirect("a_rewards:index")

                try:
                    points_value = max(0, int(points_raw))
                except (TypeError, ValueError):
                    points_value = 0

                Reward.objects.create(
                    name=name,
                    description=description,
                    points=points_value,
                    family=family,
                    created_by=user,
                )
                # Increment usage counter
                increment_usage(family, 'rewards', 1)

        elif action == "update" and is_parent:
            reward = _get_reward()
            if reward:
                reward.name = request.POST.get("name", reward.name).strip() or reward.name
                reward.description = request.POST.get("description", reward.description).strip()
                try:
                    reward.points = max(0, int(request.POST.get("points", reward.points)))
                except (TypeError, ValueError):
                    pass
                reward.save()

        elif action == "delete" and is_parent:
            reward = _get_reward()
            if reward:
                reward.delete()

        elif action == "unclaim" and is_parent:
            reward = _get_reward()
            if reward and reward.claimed:
                claimer_profile = _get_or_create_profile(reward.claimed_by)
                if claimer_profile:
                    claimer_profile.points += reward.points
                    claimer_profile.save(update_fields=["points"])
                reward.claimed = False
                reward.claimed_by = None
                reward.claimed_at = None
                reward.save(update_fields=["claimed", "claimed_by", "claimed_at"])

        elif action == "claim" and is_child:
            reward = _get_reward()
            if reward and not reward.claimed and profile and profile.points >= reward.points:
                reward.claimed = True
                reward.claimed_by = user
                reward.claimed_at = timezone.now()
                reward.save(update_fields=["claimed", "claimed_by", "claimed_at"])

                profile.points = max(0, profile.points - reward.points)
                profile.save(update_fields=["points"])

        return redirect("a_rewards:index")

    if family:
        rewards_qs = Reward.objects.filter(family=family).select_related(
            "claimed_by__family_profile",
            "created_by__family_profile",
        )
        available_rewards = list(rewards_qs.filter(claimed=False))
        claimed_rewards = list(rewards_qs.filter(claimed=True))

        for reward in itertools.chain(available_rewards, claimed_rewards):
            reward.can_claim = bool(is_child and not reward.claimed and profile and profile.points >= reward.points)
            reward.points_shortfall = reward.points - (profile.points if profile else 0)

    else:
        available_rewards = []
        claimed_rewards = []

    if profile:
        points_balance = profile.points
    elif is_parent and family:
        child_profiles = UserProfile.objects.filter(user__in=family.members.all(), role=UserProfile.ROLE_CHILD)
        points_balance = sum(child_profiles.values_list("points", flat=True))
    else:
        points_balance = 0

    context = {
        "family": family,
        "profile": profile,
        "role": role,
        "is_parent": is_parent,
        "is_child": is_child,
        "has_family": family is not None,
        "points_balance": points_balance,
        "available_rewards": available_rewards,
        "claimed_rewards": claimed_rewards,
    }
    return render(request, "a_rewards/index.html", context)
