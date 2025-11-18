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

    # Handle form submissions
    if request.method == 'POST':
        form_type = request.POST.get('form_type')
        
        # Handle profile update
        if form_type == 'profile':
            display_name = request.POST.get('display_name', '').strip()
            email = request.POST.get('email', '').strip()
            role = request.POST.get('role')
            
            # Update display name (first_name and last_name)
            if display_name:
                name_parts = display_name.split(' ', 1)
                user.first_name = name_parts[0]
                user.last_name = name_parts[1] if len(name_parts) > 1 else ''
                user.save(update_fields=['first_name', 'last_name'])
            
            # Update email
            if email and email != user.email:
                # Check if email is already in use
                if User.objects.filter(email=email).exclude(id=user.id).exists():
                    messages.error(request, "See e-posti aadress on juba kasutusel.")
                else:
                    user.email = email
                    user.save(update_fields=['email'])
                    messages.success(request, "E-posti aadress uuendatud.")
            
            # Update role (only if user is parent and changing their own role)
            if role and is_parent and role in [User.ROLE_PARENT, User.ROLE_CHILD]:
                user.role = role
                user.save(update_fields=['role'])
                messages.success(request, "Profiil uuendatud.")
            
            if not email or email == user.email:
                messages.success(request, "Profiil uuendatud.")
            return redirect('a_dashboard:settings')
        
        # Handle notification preferences
        elif form_type == 'notifications':
            notify_tasks = request.POST.get('notify_tasks') == 'on'
            notify_rewards = request.POST.get('notify_rewards') == 'on'
            notify_shopping = request.POST.get('notify_shopping') == 'on'
            notify_summary = request.POST.get('notify_summary') == 'on'
            
            # Store notification preferences
            prefs = {
                'task_updates': notify_tasks,
                'reward_updates': notify_rewards,
                'shopping_updates': notify_shopping,
                'weekly_summary': notify_summary,
            }
            user.notification_preferences = prefs
            user.save(update_fields=['notification_preferences'])
            messages.success(request, "Teavituste eelistused salvestatud.")
            return redirect('a_dashboard:settings')
        
        # Handle subscription actions (only for family owners)
        elif form_type == 'subscription' and can_manage_subscription:
            action = request.POST.get('subscription_action')
            
            if action == 'downgrade':
                # Downgrade to FREE tier
                subscription = Subscription.objects.filter(
                    owner=user,
                    tier__in=[Subscription.TIER_STARTER, Subscription.TIER_PRO]
                ).first()
                
                if not subscription or not subscription.stripe_subscription_id:
                    messages.error(request, "Aktiivset tellimust ei leitud.")
                    return redirect('a_dashboard:settings')
                
                if not django_settings.STRIPE_SECRET_KEY:
                    messages.error(request, "Stripe pole seadistatud. Palun võta ühendust toega.")
                    return redirect('a_dashboard:settings')
                
                stripe.api_key = django_settings.STRIPE_SECRET_KEY
                
                try:
                    # Cancel the Stripe subscription (at period end to keep access until then)
                    stripe.Subscription.modify(
                        subscription.stripe_subscription_id,
                        cancel_at_period_end=True,
                    )
                    
                    # Update local subscription - keep tier until period_end, then it will revert to FREE via webhook
                    subscription.status = Subscription.STATUS_CANCELLED
                    subscription.save()
                    
                    messages.success(request, "Tellimus tühistati. Juurdepääs jääb kehtima kuni arveldusperioodi lõpuni.")
                    logger.info(f"Subscription {subscription.id} cancelled for user {user.id}")
                    return redirect('a_dashboard:settings')
                    
                except stripe.error.StripeError as e:
                    messages.error(request, f"Tellimuse tühistamisel tekkis viga: {str(e)}")
                    logger.error(f"Error cancelling subscription: {str(e)}", exc_info=True)
                    return redirect('a_dashboard:settings')
            
            elif action == 'edit_portal':
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
                    # Get existing subscription
                    existing_subscription = Subscription.objects.filter(
                        owner=user,
                        tier__in=[Subscription.TIER_STARTER, Subscription.TIER_PRO]
                    ).first()
                    
                    # Get or create Stripe customer - check by email first to avoid duplicates
                    customer_id = existing_subscription.stripe_customer_id if existing_subscription else None
                    
                    if not customer_id:
                        # Try to find existing customer by email
                        try:
                            customers = stripe.Customer.list(email=user.email, limit=1)
                            if customers.data:
                                customer_id = customers.data[0].id
                                logger.info(f"Found existing Stripe customer {customer_id} for email {user.email}")
                            else:
                                # Create new customer
                                customer = stripe.Customer.create(
                                    email=user.email,
                                    metadata={'user_id': str(user.id), 'family_id': str(family.id)}
                                )
                                customer_id = customer.id
                                logger.info(f"Created new Stripe customer {customer_id} for user {user.id}")
                        except stripe.error.StripeError as e:
                            logger.error(f"Error finding/creating customer: {str(e)}")
                            messages.error(request, f"Kliendi loomisel tekkis viga: {str(e)}")
                            return redirect('a_dashboard:settings')
                    else:
                        try:
                            customer = stripe.Customer.retrieve(customer_id)
                        except stripe.error.StripeError:
                            # Customer doesn't exist, create new one
                            customer = stripe.Customer.create(
                                email=user.email,
                                metadata={'user_id': str(user.id), 'family_id': str(family.id)}
                            )
                            customer_id = customer.id
                            logger.info(f"Recreated Stripe customer {customer_id} for user {user.id}")
                    
                    # If user has an active subscription, update it directly with proration
                    if existing_subscription and existing_subscription.stripe_subscription_id and existing_subscription.is_active():
                        try:
                            # Retrieve the Stripe subscription
                            stripe_subscription = stripe.Subscription.retrieve(existing_subscription.stripe_subscription_id)
                            
                            # Get the current subscription item ID
                            subscription_item_id = stripe_subscription['items']['data'][0]['id']
                            
                            # Update subscription with new price (prorated)
                            updated_subscription = stripe.Subscription.modify(
                                existing_subscription.stripe_subscription_id,
                                items=[{
                                    'id': subscription_item_id,
                                    'price': price_id,
                                }],
                                proration_behavior='always',  # Always prorate when changing plans
                                metadata={
                                    'user_id': str(user.id),
                                    'family_id': str(family.id),
                                    'tier': tier,
                                }
                            )
                            
                            # Update local subscription record
                            existing_subscription.tier = tier
                            existing_subscription.status = updated_subscription.status
                            if updated_subscription.current_period_start:
                                existing_subscription.current_period_start = timezone.make_aware(
                                    datetime.fromtimestamp(updated_subscription.current_period_start)
                                )
                            if updated_subscription.current_period_end:
                                existing_subscription.current_period_end = timezone.make_aware(
                                    datetime.fromtimestamp(updated_subscription.current_period_end)
                                )
                            existing_subscription.save()
                            
                            messages.success(request, f"Pakett uuendati tasemele {existing_subscription.get_tier_display()}! Maksed on proportsionaalsed.")
                            return redirect('a_dashboard:settings')
                            
                        except stripe.error.StripeError as e:
                            messages.error(request, f"Tellimuse uuendamisel tekkis viga: {str(e)}")
                            return redirect('a_dashboard:settings')
                    
                    # No active subscription - create new one via checkout
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
                            'user_id': str(user.id),
                            'family_id': str(family.id),
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

    # Load notification preferences from user model, with defaults
    notification_preferences = user.notification_preferences or {
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