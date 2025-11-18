import stripe
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Sum, Q
from django.shortcuts import redirect, render
from django.utils import timezone
from django.conf import settings as django_settings

from a_family.models import Family, User
from a_rewards.models import Reward
from a_shopping.models import ShoppingListItem
from a_tasks.models import Task
from a_subscription.models import Subscription
from a_subscription.utils import (
    get_family_subscription,
    get_current_month_usage,
    get_tier_limits,
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
        {
            "label": "Ostunimekiri",
            "description": "Halda pere sisseoste ja vajalikke tooteid",
            "url": "a_shopping:index",
            "icon": "cart",
        },
    ]

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

            display_name = member.get_full_name() or member.username
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
    user = request.user
    family = _get_family_for_user(user)

    # Set default role for owner if not set
    if family and family.owner_id == user.id and not user.role:
        user.role = User.ROLE_PARENT
        user.save(update_fields=['role'])

    is_parent = user.role == User.ROLE_PARENT
    is_child = user.role == User.ROLE_CHILD

    # Only family owner can manage subscription
    can_manage_subscription = family and family.owner == user

    # Check if we should show upgrade modal (from shopping redirect)
    show_upgrade_modal = request.GET.get('upgrade') == '1'

    # Handle subscription actions
    if request.method == 'POST' and can_manage_subscription:
        action = request.POST.get('subscription_action')
        
        if action == 'edit_portal':
            subscription = Subscription.objects.filter(
                owner=user,
                tier__in=[Subscription.TIER_STARTER, Subscription.TIER_PRO]
            ).first()
            
            if not subscription or not subscription.stripe_customer_id:
                messages.error(request, "Tellimust pole või Stripe kliendi ID puudub.")
                return redirect('a_dashboard:settings')
            
            if not django_settings.STRIPE_SECRET_KEY:
                messages.error(request, "Stripe pole seadistatud. Palun võta ühendust toega.")
                return redirect('a_dashboard:settings')
            
            stripe.api_key = django_settings.STRIPE_SECRET_KEY
            
            try:
                # Create customer portal session
                portal_session = stripe.billing_portal.Session.create(
                    customer=subscription.stripe_customer_id,
                    return_url=request.build_absolute_uri('/dashboard/settings/'),
                )
                
                return redirect(portal_session.url)
                
            except stripe.error.StripeError as e:
                messages.error(request, f"Stripe'i viga: {str(e)}")
                return redirect('a_dashboard:settings')
        
        elif action == 'upgrade':
            tier = request.POST.get('tier')
            billing_period = request.POST.get('billing_period', 'monthly')
            
            if tier not in [Subscription.TIER_STARTER, Subscription.TIER_PRO]:
                messages.error(request, "Vigane paketivalik.")
                return redirect('a_dashboard:settings')
            
            # Get appropriate price ID
            if tier == Subscription.TIER_STARTER:
                price_id = django_settings.STARTER_MONTHLY_PRICE_ID if billing_period == 'monthly' else django_settings.STARTER_YEARLY_PRICE_ID
            else:  # PRO
                price_id = django_settings.PRO_MONTHLY_PRICE_ID if billing_period == 'monthly' else django_settings.PRO_YEARLY_PRICE_ID
            
            if not django_settings.STRIPE_SECRET_KEY:
                messages.error(request, "Stripe pole seadistatud. Palun võta ühendust toega.")
                return redirect('a_dashboard:settings')
            
            stripe.api_key = django_settings.STRIPE_SECRET_KEY
            
            try:
                # Get or create Stripe customer
                subscription = Subscription.objects.filter(owner=user).first()
                customer_id = subscription.stripe_customer_id if subscription else None
                
                if not customer_id:
                    customer = stripe.Customer.create(
                        email=user.email,
                        metadata={'user_id': user.id, 'family_id': family.id}
                    )
                    customer_id = customer.id
                else:
                    customer = stripe.Customer.retrieve(customer_id)
                
                # Create checkout session
                checkout_session = stripe.checkout.Session.create(
                    customer=customer_id,
                    payment_method_types=['card'],
                    line_items=[{
                        'price': price_id,
                        'quantity': 1,
                    }],
                    mode='subscription',
                    success_url=request.build_absolute_uri('/subscription/success/') + '?session_id={CHECKOUT_SESSION_ID}',
                    cancel_url=request.build_absolute_uri('/dashboard/settings/'),
                    metadata={
                        'user_id': user.id,
                        'family_id': family.id,
                        'tier': tier,
                    }
                )
                
                return redirect(checkout_session.url)
                
            except stripe.error.StripeError as e:
                messages.error(request, f"Stripe'i viga: {str(e)}")
                return redirect('a_dashboard:settings')

    # Get subscription data if user can manage it
    subscription_data = None
    if can_manage_subscription:
        tier = get_family_subscription(family)
        
        subscription = Subscription.objects.filter(
            owner=user,
            tier__in=[Subscription.TIER_STARTER, Subscription.TIER_PRO]
        ).first()
        
        subscription_data = {
            'tier': tier,
            'display_tier': dict(Subscription.TIER_CHOICES).get(tier, tier),
            'subscription': subscription,
        }

    notification_preferences = {
        "task_updates": True,
        "reward_updates": True,
        "shopping_updates": False,
        "weekly_summary": True,
    }

    context = {
        "family": family,
        "is_parent": is_parent,
        "is_child": is_child,
        "settings_user": user,
        "role_parent": User.ROLE_PARENT,
        "role_child": User.ROLE_CHILD,
        "current_role": user.role,
        "notification_preferences": notification_preferences,
        "subscription_data": subscription_data,
        "can_manage_subscription": can_manage_subscription,
        "show_upgrade_modal": show_upgrade_modal,
    }
    return render(request, 'a_dashboard/settings.html', context)