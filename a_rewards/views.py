# Standard library imports
import itertools

# Django imports
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.conf import settings
from django.db import transaction
from django.shortcuts import redirect, render
from django.utils import timezone

# Local application imports
from a_family.models import Family, User
from a_family.emails import send_reward_claimed_notification
from a_family.utils import get_family_for_user as _get_family_for_user
from a_subscription.utils import check_subscription_limit, increment_usage

from .models import Reward


def _ensure_user_role(user, default_role=User.ROLE_CHILD):
    """Ensure user has a role set, defaulting to the provided role if not set"""
    if user and not user.role:
        user.role = default_role
        user.save(update_fields=['role'])
    return user


@login_required
def index(request):
    user = request.user
    family = _get_family_for_user(user)

    # Redirect to onboarding if user doesn't have a family
    if not family:
        messages.info(request, "Perega liitumiseks või uue pere loomiseks palun täida pere andmed.")
        return redirect('a_family:onboarding')

    # Set default role for owner if not set
    if family and family.owner_id == user.id and not user.role:
        user.role = User.ROLE_PARENT
        user.save(update_fields=['role'])

    role = user.role or (User.ROLE_PARENT if family and family.owner_id == user.id else None)
    is_parent = role == User.ROLE_PARENT
    is_child = role == User.ROLE_CHILD

    if request.method == "POST" and family:
        action = request.POST.get("action")
        reward_id = request.POST.get("reward_id")

        def _get_reward():
            if not reward_id:
                return None
            return Reward.objects.filter(family=family, id=reward_id).select_related("claimed_by").first()

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
                        f"Oled jõudnud oma kuise preemiapiirini ({limit} preemiat). "
                        f"Oled sel kuul loonud {current_count} preemiat. "
                        f"Palun uuenda tellimust, et lisada rohkem preemiaid."
                    )
                    return redirect("a_rewards:index")

                try:
                    points_value = max(0, int(points_raw))
                except (TypeError, ValueError):
                    points_value = 0

                # Use transaction to ensure reward creation and usage increment are atomic
                with transaction.atomic():
                    reward = Reward.objects.create(
                        name=name,
                        description=description,
                        points=points_value,
                        family=family,
                        created_by=user,
                    )
                    # Increment usage counter (within same transaction)
                    increment_usage(family, 'rewards', 1)
                # Don't send notification when reward is created, only when claimed

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
            if not reward:
                messages.error(request, f"Midagi läks valesti. Kui probleem püsib, palun võta ühendust tugiteenusega: {settings.SUPPORT_EMAIL}")
            elif not reward.claimed:
                messages.warning(request, "See preemia pole lunastatud.")
            elif not reward.claimed_by:
                messages.error(request, "Preemial pole määratud lunastajat.")
            else:
                # Use transaction to ensure atomicity
                try:
                    with transaction.atomic():
                        # Refresh from DB with row-level locking
                        reward_refreshed = Reward.objects.select_for_update().get(id=reward.id)
                        if reward_refreshed.claimed_by:
                            claimed_by = User.objects.select_for_update().get(id=reward_refreshed.claimed_by.id)
                            claimed_by.points += reward_refreshed.points
                            claimed_by.save(update_fields=["points"])
                        
                        reward_refreshed.claimed = False
                        reward_refreshed.claimed_by = None
                        reward_refreshed.claimed_at = None
                        reward_refreshed.save(update_fields=["claimed", "claimed_by", "claimed_at"])
                        messages.success(request, f"Preemia '{reward_refreshed.name}' lunastamine tühistatud.")
                except Exception as e:
                    messages.error(request, f"Midagi läks valesti. Kui probleem püsib, palun võta ühendust tugiteenusega: {settings.SUPPORT_EMAIL}")

        elif action == "claim" and is_child:
            reward = _get_reward()
            if not reward:
                messages.error(request, f"Midagi läks valesti. Kui probleem püsib, palun võta ühendust tugiteenusega: {settings.SUPPORT_EMAIL}")
            elif reward.claimed:
                messages.warning(request, "See preemia on juba lunastatud.")
            else:
                # Use transaction to prevent race conditions
                try:
                    with transaction.atomic():
                        # Refresh user and reward from DB with row-level locking
                        user_refreshed = User.objects.select_for_update().get(id=user.id)
                        reward_refreshed = Reward.objects.select_for_update().get(id=reward.id)
                        
                        # Double-check conditions after locking
                        if reward_refreshed.claimed:
                            messages.warning(request, "See preemia on juba lunastatud.")
                        elif user_refreshed.points < reward_refreshed.points:
                            messages.error(
                                request,
                                f"Sul pole piisavalt punkte. Vajad {reward_refreshed.points} punkti, "
                                f"aga sul on ainult {user_refreshed.points} punkti."
                            )
                        else:
                            # Claim the reward
                            reward_refreshed.claimed = True
                            reward_refreshed.claimed_by = user_refreshed
                            reward_refreshed.claimed_at = timezone.now()
                            reward_refreshed.save(update_fields=["claimed", "claimed_by", "claimed_at"])

                            # Deduct points
                            user_refreshed.points = max(0, user_refreshed.points - reward_refreshed.points)
                            user_refreshed.save(update_fields=["points"])
                            messages.success(request, f"Preemia '{reward_refreshed.name}' lunastatud!")
                            
                            # Send notification email
                            try:
                                send_reward_claimed_notification(request, reward_refreshed)
                            except Exception as e:
                                import logging
                                logger = logging.getLogger(__name__)
                                logger.warning(f"Failed to send reward claimed notification: {e}", exc_info=True)
                except User.DoesNotExist:
                    messages.error(request, f"Midagi läks valesti. Kui probleem püsib, palun võta ühendust tugiteenusega: {settings.SUPPORT_EMAIL}")
                except Reward.DoesNotExist:
                    messages.error(request, f"Midagi läks valesti. Kui probleem püsib, palun võta ühendust tugiteenusega: {settings.SUPPORT_EMAIL}")
                except Exception as e:
                    messages.error(request, f"Midagi läks valesti. Kui probleem püsib, palun võta ühendust tugiteenusega: {settings.SUPPORT_EMAIL}")

        return redirect("a_rewards:index")

    if family:
        rewards_qs = Reward.objects.filter(family=family).select_related(
            "claimed_by",
            "created_by",
        )
        available_rewards = list(rewards_qs.filter(claimed=False))
        claimed_rewards = list(rewards_qs.filter(claimed=True))

        for reward in itertools.chain(available_rewards, claimed_rewards):
            reward.can_claim = bool(is_child and not reward.claimed and user.points >= reward.points)
            reward.points_shortfall = reward.points - user.points

    else:
        available_rewards = []
        claimed_rewards = []

    if is_parent and family:
        # Use values_list to avoid loading full objects when we only need points
        child_users = family.members.filter(role=User.ROLE_CHILD)
        points_balance = sum(child_users.values_list("points", flat=True))
    else:
        points_balance = user.points

    context = {
        "family": family,
        "role": role,
        "is_parent": is_parent,
        "is_child": is_child,
        "has_family": family is not None,
        "points_balance": points_balance,
        "available_rewards": available_rewards,
        "claimed_rewards": claimed_rewards,
    }
    return render(request, "a_rewards/index.html", context)
