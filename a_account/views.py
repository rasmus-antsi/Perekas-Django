import logging
import stripe
from datetime import datetime
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.utils import timezone
from django.conf import settings as django_settings

logger = logging.getLogger(__name__)

from a_family.models import Family, User
from a_subscription.models import Subscription
from a_subscription.utils import get_family_subscription


def _get_family_for_user(user):
    family = None
    if hasattr(user, "families"):
        family = user.families.first()
    if family is None:
        family = Family.objects.filter(owner=user).first()
    return family


@login_required
def settings_base(request):
    """Main settings page with sidebar navigation"""
    user = request.user
    family = _get_family_for_user(user)

    # Set default role for owner if not set
    if family and family.owner_id == user.id and not user.role:
        user.role = User.ROLE_PARENT
        user.save(update_fields=['role'])

    # Only family owner can manage subscription
    can_manage_subscription = False
    if family is not None:
        try:
            can_manage_subscription = family.owner == user
        except (AttributeError, ValueError):
            can_manage_subscription = False

    # Get current section from URL parameter (default to 'general')
    current_section = request.GET.get('section', 'general')
    if current_section not in ['general', 'notifications', 'subscriptions']:
        current_section = 'general'

    # Redirect to appropriate section view
    if current_section == 'general':
        return general_settings(request)
    elif current_section == 'notifications':
        return notification_settings(request)
    elif current_section == 'subscriptions':
        return subscription_settings(request)


@login_required
def general_settings(request):
    """General account settings"""
    user = request.user
    family = _get_family_for_user(user)

    # Set default role for owner if not set
    if family and family.owner_id == user.id and not user.role:
        user.role = User.ROLE_PARENT
        user.save(update_fields=['role'])

    is_parent = user.role == User.ROLE_PARENT

    # Only family owner can manage subscription
    can_manage_subscription = False
    if family is not None:
        try:
            can_manage_subscription = family.owner == user
        except (AttributeError, ValueError):
            can_manage_subscription = False

    # Handle form submission
    if request.method == 'POST' and request.POST.get('form_type') == 'profile':
        first_name = request.POST.get('first_name', '').strip()
        last_name = request.POST.get('last_name', '').strip()
        email = request.POST.get('email', '').strip()
        role = request.POST.get('role')
        updated_fields = set()
        
        # Update first and last name
        if first_name != user.first_name:
            user.first_name = first_name
            updated_fields.add('first_name')

        if last_name != user.last_name:
            user.last_name = last_name
            updated_fields.add('last_name')
        
        # Update email
        if email and email != user.email:
            # Check if email is already in use
            if User.objects.filter(email=email).exclude(id=user.id).exists():
                messages.error(request, "See e-posti aadress on juba kasutusel.")
            else:
                user.email = email
                updated_fields.add('email')
                messages.success(request, "E-posti aadress uuendatud.")
        
        # Update role (only if user is parent and changing their own role)
        if role and is_parent and role in [User.ROLE_PARENT, User.ROLE_CHILD]:
            user.role = role
            updated_fields.add('role')

        if updated_fields:
            user.save(update_fields=list(updated_fields))
            messages.success(request, "Profiil uuendatud.")
        return redirect('a_account:settings?section=general')

    # Only family owner can manage subscription
    can_manage_subscription = False
    if family is not None:
        try:
            can_manage_subscription = family.owner == user
        except (AttributeError, ValueError):
            can_manage_subscription = False

    context = {
        "family": family,
        "is_parent": is_parent,
        "settings_user": user,
        "role_parent": User.ROLE_PARENT,
        "role_child": User.ROLE_CHILD,
        "current_role": user.role,
        "current_section": "general",
        "can_manage_subscription": can_manage_subscription,
        "user": user,
    }
    return render(request, 'a_account/general.html', context)


@login_required
def notification_settings(request):
    """Notification preferences settings"""
    user = request.user
    family = _get_family_for_user(user)

    # Only family owner can manage subscription
    can_manage_subscription = False
    if family is not None:
        try:
            can_manage_subscription = family.owner == user
        except (AttributeError, ValueError):
            can_manage_subscription = False

    # Handle form submission
    if request.method == 'POST' and request.POST.get('form_type') == 'notifications':
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
        return redirect('a_account:settings?section=notifications')

    # Load notification preferences from user model, with defaults
    user_prefs = user.notification_preferences or {}
    notification_preferences = {
        "task_updates": user_prefs.get("task_updates", True),
        "reward_updates": user_prefs.get("reward_updates", True),
        "shopping_updates": user_prefs.get("shopping_updates", False),
        "weekly_summary": user_prefs.get("weekly_summary", True),
    }

    context = {
        "notification_preferences": notification_preferences,
        "current_section": "notifications",
        "can_manage_subscription": can_manage_subscription,
        "user": user,
    }
    return render(request, 'a_account/notifications.html', context)


@login_required
def subscription_settings(request):
    """Subscription management settings"""
    user = request.user
    family = _get_family_for_user(user)

    # Only family owner can manage subscription
    can_manage_subscription = False
    if family is not None:
        try:
            can_manage_subscription = family.owner == user
        except (AttributeError, ValueError):
            can_manage_subscription = False

    # Check if we should show upgrade modal (from shopping redirect)
    show_upgrade_modal = request.GET.get('upgrade') == '1'

    # Handle form submissions
    if request.method == 'POST' and request.POST.get('form_type') == 'subscription' and can_manage_subscription:
        action = request.POST.get('subscription_action')
        
        if action == 'downgrade':
            # Redirect to Stripe customer portal for downgrade/cancellation
            subscription = Subscription.objects.filter(
                owner=user,
                tier__in=[Subscription.TIER_STARTER, Subscription.TIER_PRO]
            ).first()
            
            if not subscription:
                messages.error(request, "Tellimust ei leitud.")
                return redirect('a_account:settings?section=subscriptions')
            
            if not hasattr(subscription, 'stripe_customer_id') or not subscription.stripe_customer_id:
                messages.error(request, "Stripe kliendi ID puudub.")
                return redirect('a_account:settings?section=subscriptions')
            
            if not django_settings.STRIPE_SECRET_KEY:
                messages.error(request, "Stripe pole seadistatud. Palun võta ühendust toega.")
                return redirect('a_account:settings?section=subscriptions')
            
            stripe.api_key = django_settings.STRIPE_SECRET_KEY
            
            try:
                # Create customer portal session for managing subscription
                portal_params = {
                    'customer': subscription.stripe_customer_id,
                    'return_url': request.build_absolute_uri('/account/settings/?section=subscriptions'),
                    'locale': 'et',
                }
                
                # Only add configuration if it's set (optional parameter)
                if hasattr(django_settings, 'STRIPE_CUSTOMER_PORTAL_ID') and django_settings.STRIPE_CUSTOMER_PORTAL_ID:
                    portal_params['configuration'] = django_settings.STRIPE_CUSTOMER_PORTAL_ID
                
                portal_session = stripe.billing_portal.Session.create(**portal_params)
                
                return redirect(portal_session.url)
                
            except AttributeError as e:
                # Handle case where billing_portal API might not be available
                logger.error(f"Stripe billing_portal API not available: {str(e)}", exc_info=True)
                messages.error(request, "Stripe'i kliendiportaali API pole saadaval. Palun kontrolli Stripe konfiguratsiooni.")
                return redirect('a_account:settings?section=subscriptions')
            except stripe.error.StripeError as e:
                messages.error(request, f"Stripe'i viga: {str(e)}")
                logger.error(f"Stripe error: {str(e)}", exc_info=True)
                return redirect('a_account:settings?section=subscriptions')
        
        elif action == 'edit_portal':
            subscription = Subscription.objects.filter(
                owner=user,
                tier__in=[Subscription.TIER_STARTER, Subscription.TIER_PRO]
            ).first()
            
            if not subscription:
                messages.error(request, "Tellimust ei leitud.")
                return redirect('a_account:settings?section=subscriptions')
            
            if not hasattr(subscription, 'stripe_customer_id') or not subscription.stripe_customer_id:
                messages.error(request, "Stripe kliendi ID puudub.")
                return redirect('a_account:settings?section=subscriptions')
            
            if not django_settings.STRIPE_SECRET_KEY:
                messages.error(request, "Stripe pole seadistatud. Palun võta ühendust toega.")
                return redirect('a_account:settings?section=subscriptions')
            
            stripe.api_key = django_settings.STRIPE_SECRET_KEY
            
            try:
                # Create customer portal session
                # First check if billing_portal exists by trying to access it
                try:
                    billing_portal = stripe.billing_portal
                except AttributeError:
                    logger.error("Stripe billing_portal API not available in this Stripe SDK version")
                    messages.error(request, "Stripe'i kliendiportaali API pole sinu Stripe versioonis toetatud.")
                    return redirect('a_account:settings?section=subscriptions')
                
                # Check if configuration ID is set
                portal_params = {
                    'customer': subscription.stripe_customer_id,
                    'return_url': request.build_absolute_uri('/account/settings/?section=subscriptions'),
                    'locale': 'et',
                }
                
                # Only add configuration if it's set (optional parameter)
                if hasattr(django_settings, 'STRIPE_CUSTOMER_PORTAL_ID') and django_settings.STRIPE_CUSTOMER_PORTAL_ID:
                    portal_params['configuration'] = django_settings.STRIPE_CUSTOMER_PORTAL_ID
                
                # Create billing portal session
                portal_session = billing_portal.Session.create(**portal_params)
                
                return redirect(portal_session.url)
                
            except AttributeError as e:
                # Handle case where billing_portal API might not be available
                logger.error(f"Stripe billing_portal API not available: {str(e)}", exc_info=True)
                messages.error(request, "Stripe'i kliendiportaali API pole saadaval. Palun kontrolli Stripe konfiguratsiooni.")
                return redirect('a_account:settings?section=subscriptions')
            except stripe.error.StripeError as e:
                messages.error(request, f"Stripe'i viga: {str(e)}")
                logger.error(f"Stripe error: {str(e)}", exc_info=True)
                return redirect('a_account:settings?section=subscriptions')
            except Exception as e:
                logger.error(f"Unexpected error creating billing portal session: {str(e)}", exc_info=True)
                messages.error(request, f"Viga portaali loomisel: {str(e)}")
                return redirect('a_account:settings?section=subscriptions')
        
        elif action == 'upgrade':
            tier = request.POST.get('tier')
            billing_period = request.POST.get('billing_period', 'monthly')
            
            if tier not in [Subscription.TIER_STARTER, Subscription.TIER_PRO]:
                messages.error(request, "Vigane paketivalik.")
                return redirect('a_account:settings?section=subscriptions')
            
            # Get appropriate price ID
            if tier == Subscription.TIER_STARTER:
                price_id = django_settings.STARTER_MONTHLY_PRICE_ID if billing_period == 'monthly' else django_settings.STARTER_YEARLY_PRICE_ID
            else:  # PRO
                price_id = django_settings.PRO_MONTHLY_PRICE_ID if billing_period == 'monthly' else django_settings.PRO_YEARLY_PRICE_ID
            
            if not django_settings.STRIPE_SECRET_KEY:
                messages.error(request, "Stripe pole seadistatud. Palun võta ühendust toega.")
                return redirect('a_account:settings?section=subscriptions')
            
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
                        return redirect('a_account:settings?section=subscriptions')
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
                        return redirect('a_account:settings?section=subscriptions')
                        
                    except stripe.error.StripeError as e:
                        messages.error(request, f"Tellimuse uuendamisel tekkis viga: {str(e)}")
                        return redirect('a_account:settings?section=subscriptions')
                
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
                    cancel_url=request.build_absolute_uri('/account/settings/?section=subscriptions'),
                    locale='et',
                    metadata={
                        'user_id': str(user.id),
                        'family_id': str(family.id),
                        'tier': tier,
                    }
                )
                
                return redirect(checkout_session.url)
                
            except stripe.error.StripeError as e:
                messages.error(request, f"Stripe'i viga: {str(e)}")
                return redirect('a_account:settings?section=subscriptions')

    # Get subscription data if user can manage it
    subscription_data = None
    if can_manage_subscription and family:
        try:
            tier = get_family_subscription(family)
            if not tier:
                tier = Subscription.TIER_FREE
            
            subscription = Subscription.objects.filter(
                owner=user,
                tier__in=[Subscription.TIER_STARTER, Subscription.TIER_PRO]
            ).first()
            
            # Get display tier safely
            tier_choices = dict(Subscription.TIER_CHOICES)
            display_tier = tier_choices.get(tier, tier)
            if not display_tier:
                display_tier = tier_choices.get(Subscription.TIER_FREE, Subscription.TIER_FREE)
            
            subscription_data = {
                'tier': tier,
                'display_tier': display_tier,
                'subscription': subscription,
            }
        except Exception as e:
            logger.error(f"Error loading subscription data: {str(e)}", exc_info=True)
            tier_choices = dict(Subscription.TIER_CHOICES)
            subscription_data = {
                'tier': Subscription.TIER_FREE,
                'display_tier': tier_choices.get(Subscription.TIER_FREE, Subscription.TIER_FREE),
                'subscription': None,
            }

    context = {
        "subscription_data": subscription_data,
        "can_manage_subscription": can_manage_subscription,
        "show_upgrade_modal": show_upgrade_modal,
        "current_section": "subscriptions",
        "family": family,
        "user": user,
    }
    return render(request, 'a_account/subscriptions.html', context)

