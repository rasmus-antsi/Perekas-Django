# Standard library imports
import logging
from datetime import datetime

# Third-party imports
import stripe

# Django imports
from django.conf import settings as django_settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils import timezone

# Local application imports
from a_family.models import Family, User
from a_subscription.models import Subscription
from a_subscription.utils import get_family_subscription, get_tier_from_price_id
from a_api.meta_capi import (
    MetaCapiConfigError,
    MetaCapiSendError,
    build_event_payload,
    build_user_data,
    default_event_id,
    default_event_time,
    send_events_to_meta,
)

logger = logging.getLogger(__name__)


def _client_ip(request):
    forwarded = request.META.get('HTTP_X_FORWARDED_FOR')
    if forwarded:
        return forwarded.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR')


def _send_meta_event(request, *, event_name, event_source_url, email=None, custom_data=None, event_id=None, attribution_data=None, original_event_data=None):
    client_ip = _client_ip(request)
    client_user_agent = request.META.get('HTTP_USER_AGENT', '')
    user_data = build_user_data(email, client_ip, client_user_agent)
    payload = build_event_payload(
        event_name=event_name,
        event_time=default_event_time(),
        event_source_url=event_source_url,
        action_source='website',
        event_id=event_id or default_event_id(),
        user_data=user_data,
        custom_data=custom_data or None,
        attribution_data=attribution_data,
        original_event_data=original_event_data,
    )
    try:
        send_events_to_meta([payload])
    except (MetaCapiConfigError, MetaCapiSendError, Exception):
        return None
    return payload.get('event_id')


def _get_billing_period_from_price_id(price_id):
    """Get billing period (monthly/yearly) from Stripe price ID"""
    if not price_id:
        return None
    
    monthly_price_ids = [
        getattr(django_settings, 'STARTER_MONTHLY_PRICE_ID', None),
        getattr(django_settings, 'PRO_MONTHLY_PRICE_ID', None),
    ]
    
    yearly_price_ids = [
        getattr(django_settings, 'STARTER_YEARLY_PRICE_ID', None),
        getattr(django_settings, 'PRO_YEARLY_PRICE_ID', None),
    ]
    
    if price_id in monthly_price_ids:
        return 'monthly'
    elif price_id in yearly_price_ids:
        return 'yearly'
    
    return None


def _get_promo_code_for_tier(tier):
    """
    Map subscription tier to Stripe promotion code ID.
    These promotion codes are configured in Stripe to be single-use per customer.
    """
    if tier == Subscription.TIER_STARTER:
        return 'promo_1SeZ0o7Bxzw7NSMsOLqkTz71'  # coupon 994URhEg
    if tier == Subscription.TIER_PRO:
        return 'promo_1SeYcP7Bxzw7NSMsXzDMN6ed'  # coupon igyReatB
    return None


def _sanitize_error_message(error_msg):
    """Always return generic user-friendly error message"""
    return f"Midagi läks valesti. Kui probleem püsib, palun võta ühendust tugiteenusega: {django_settings.SUPPORT_EMAIL}"


from a_family.utils import get_family_for_user as _get_family_for_user


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
    
    # Redirect notifications section to general if user has no email
    if current_section == 'notifications' and not user.email:
        messages.info(request, "Teavituste seadistamiseks peab teil olema e-posti aadress.")
        return redirect(f"{reverse('a_account:settings')}?section=general")

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
    if request.method == 'POST':
        form_type = request.POST.get('form_type')
        
        if form_type == 'profile':
            from datetime import datetime
            username = request.POST.get('username', '').strip()
            first_name = request.POST.get('first_name', '').strip()
            last_name = request.POST.get('last_name', '').strip()
            birthdate_str = request.POST.get('birthdate', '').strip()
            role = request.POST.get('role')
            updated_fields = set()
            
            # Update username - check for uniqueness
            if username and username != user.username:
                # Check if username is already in use
                if User.objects.filter(username=username).exclude(id=user.id).exists():
                    messages.error(request, "See kasutajanimi on juba kasutusel.")
                    return redirect(f"{reverse('a_account:settings')}?section=general")
                
                # Validate username format (Django username requirements)
                if len(username) < 1:
                    messages.error(request, "Kasutajanimi peab olema vähemalt 1 märk pikk.")
                    return redirect(f"{reverse('a_account:settings')}?section=general")
                
                user.username = username
                updated_fields.add('username')
                messages.success(request, "Kasutajanimi uuendatud.")
            
            # Update first and last name
            if first_name != user.first_name:
                user.first_name = first_name
                updated_fields.add('first_name')

            if last_name != user.last_name:
                user.last_name = last_name
                updated_fields.add('last_name')
            
            # Update birthdate
            if birthdate_str:
                try:
                    birthdate = datetime.strptime(birthdate_str, '%Y-%m-%d').date()
                    if user.birthdate != birthdate:
                        user.birthdate = birthdate
                        updated_fields.add('birthdate')
                except ValueError:
                    messages.error(request, "Vale sünniaja vorming.")
                    return redirect(f"{reverse('a_account:settings')}?section=general")
            elif user.birthdate:
                # Allow clearing birthdate
                user.birthdate = None
                updated_fields.add('birthdate')
            
            # Update email - only allow parents to change email
            if is_parent:
                email = request.POST.get('email', '').strip()
                
                if email and email != user.email:
                    # Check if email is already in use
                    if User.objects.filter(email=email).exclude(id=user.id).exists():
                        messages.error(request, "See e-posti aadress on juba kasutusel.")
                    else:
                        # Update email
                        user.email = email
                        updated_fields.add('email')
                        
                        # Update EmailAddress records
                        try:
                            from allauth.account.models import EmailAddress
                            # Remove old email address if exists
                            if user.email:
                                EmailAddress.objects.filter(email=user.email, user=user).exclude(email=email).delete()
                            # Create or update EmailAddress
                            email_address, created = EmailAddress.objects.get_or_create(
                                email=email,
                                user=user,
                                defaults={'primary': True, 'verified': True}
                            )
                            if not created:
                                email_address.primary = True
                                email_address.verified = True
                                email_address.save()
                        except Exception:
                            pass
                elif not email and user.email:
                    # Allow clearing email only for parents
                    user.email = None
                    updated_fields.add('email')
                    # Remove email address records
                    try:
                        from allauth.account.models import EmailAddress
                        EmailAddress.objects.filter(user=user).delete()
                    except Exception:
                        pass
            # Children cannot change their email - ignore any email POST data
            
            # Update role (only if user is parent and changing their own role)
            if role and is_parent and role in [User.ROLE_PARENT, User.ROLE_CHILD]:
                user.role = role
                updated_fields.add('role')

            # Save remaining fields (email might already be saved above)
            remaining_fields = [f for f in updated_fields if f != 'email']
            if remaining_fields:
                user.save(update_fields=remaining_fields)
                messages.success(request, "Profiil uuendatud.")
            elif updated_fields and 'email' not in updated_fields:
                # Only show message if we saved something other than email
                messages.success(request, "Profiil uuendatud.")
            return redirect(f"{reverse('a_account:settings')}?section=general")
        
        elif form_type == 'password_change':
            old_password = request.POST.get('old_password', '').strip()
            new_password1 = request.POST.get('new_password1', '').strip()
            new_password2 = request.POST.get('new_password2', '').strip()
            
            # Validate old password
            if not old_password:
                messages.error(request, "Palun sisesta praegune parool.")
                return redirect(f"{reverse('a_account:settings')}?section=general")
            
            if not user.check_password(old_password):
                messages.error(request, "Praegune parool on vale.")
                return redirect(f"{reverse('a_account:settings')}?section=general")
            
            # Validate new password
            if not new_password1 or not new_password2:
                messages.error(request, "Palun sisesta uus parool mõlemasse välja.")
                return redirect(f"{reverse('a_account:settings')}?section=general")
            
            if new_password1 != new_password2:
                messages.error(request, "Uued paroolid ei kattu.")
                return redirect(f"{reverse('a_account:settings')}?section=general")
            
            # Validate password using the same validator as signup
            from a_family.validators import SimplePasswordValidator
            validator = SimplePasswordValidator(
                min_length=8,
                require_number=True,
                require_uppercase=True,
            )
            
            try:
                validator.validate(new_password1, user=user)
            except Exception as e:
                messages.error(request, str(e))
                return redirect(f"{reverse('a_account:settings')}?section=general")
            
            # Change password
            user.set_password(new_password1)
            user.save(update_fields=['password'])
            messages.success(request, "Parool muudetud edukalt!")
            return redirect(f"{reverse('a_account:settings')}?section=general")

    # Only family owner can manage subscription
    can_manage_subscription = False
    if family is not None:
        try:
            can_manage_subscription = family.owner == user
        except (AttributeError, ValueError):
            can_manage_subscription = False

    from datetime import date
    
    children_count = 0
    has_active_subscription = False
    if family:
        children_count = family.members.filter(role=User.ROLE_CHILD).count()
        if family.owner == user:
            active_subscription = Subscription.objects.filter(
                owner=user,
                tier__in=[Subscription.TIER_STARTER, Subscription.TIER_PRO]
            ).first()
            has_active_subscription = bool(active_subscription and active_subscription.is_active())

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
        "today": date.today(),
        "has_email": bool(user.email),
        "is_family_owner": family and family.owner == user if family else False,
        "children_count": children_count,
        "has_active_subscription": has_active_subscription,
    }
    return render(request, 'a_account/general.html', context)


@login_required
def notification_settings(request):
    """Notification preferences settings"""
    user = request.user
    family = _get_family_for_user(user)

    # Redirect users without email - they can't receive notifications
    if not user.email:
        messages.info(request, "Teavituste seadistamiseks peab teil olema e-posti aadress.")
        return redirect(f"{reverse('a_account:settings')}?section=general")

    # Only family owner can manage subscription
    can_manage_subscription = False
    if family is not None:
        try:
            can_manage_subscription = family.owner == user
        except (AttributeError, ValueError):
            can_manage_subscription = False

    # Handle form submission
    if request.method == 'POST' and request.POST.get('form_type') == 'notifications':
        # Checkboxes only send 'on' when checked, otherwise they're not in POST
        notify_tasks = 'notify_tasks' in request.POST and request.POST.get('notify_tasks') == 'on'
        notify_rewards = 'notify_rewards' in request.POST and request.POST.get('notify_rewards') == 'on'
        notify_shopping = 'notify_shopping' in request.POST and request.POST.get('notify_shopping') == 'on'
        notify_summary = 'notify_summary' in request.POST and request.POST.get('notify_summary') == 'on'
        
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
        return redirect(f"{reverse('a_account:settings')}?section=notifications")

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
        "has_email": bool(user.email),
    }
    return render(request, 'a_account/notifications.html', context)


@login_required
def subscription_settings(request):
    """Subscription management settings - only for family owners"""
    user = request.user
    family = _get_family_for_user(user)

    # Only family owner can manage subscription - check access and redirect if not owner
    can_manage_subscription = False
    if family is not None:
        try:
            can_manage_subscription = family.owner == user
        except (AttributeError, ValueError):
            can_manage_subscription = False
    
    # Redirect non-owners with error message
    if not can_manage_subscription:
        # Different message for children vs non-owner parents
        if user.role == User.ROLE_CHILD:
            messages.error(request, "Tellimuste haldamine on lubatud ainult pere omanikule.")
        else:
            messages.error(request, "Tellimuste haldamiseks pead olema pere omanik.")
        # Redirect to previous page or dashboard (safely)
        referer = request.META.get('HTTP_REFERER')
        # Only redirect to referer if it's from the same site
        if referer and request.build_absolute_uri('/').split('/')[2] in referer:
            return redirect(referer)
        return redirect(reverse('a_dashboard:dashboard'))

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
                messages.error(request, _sanitize_error_message(str(e)))
                return redirect(f"{reverse('a_account:settings')}?section=subscriptions")
            
            if not hasattr(subscription, 'stripe_customer_id') or not subscription.stripe_customer_id:
                messages.error(request, _sanitize_error_message(str(e)))
                return redirect(f"{reverse('a_account:settings')}?section=subscriptions")
            
            if not django_settings.STRIPE_SECRET_KEY:
                messages.error(request, _sanitize_error_message(str(e)))
                return redirect(f"{reverse('a_account:settings')}?section=subscriptions")
            
            stripe.api_key = django_settings.STRIPE_SECRET_KEY
            
            try:
                # Build return URL - use STRIPE_BASE_URL if set, otherwise use request
                base_url = django_settings.STRIPE_BASE_URL
                if base_url:
                    # Remove trailing slash if present
                    base_url = base_url.rstrip('/')
                    return_url = f"{base_url}/account/settings/?section=subscriptions"
                else:
                    # Use request-based URL (for local development)
                    return_url = request.build_absolute_uri('/account/settings/?section=subscriptions')
                
                # Create customer portal session for managing subscription
                portal_params = {
                    'customer': subscription.stripe_customer_id,
                    'return_url': return_url,
                    'locale': 'et',
                }
                
                # Only add configuration if it's set (optional parameter)
                if hasattr(django_settings, 'STRIPE_CUSTOMER_PORTAL_ID') and django_settings.STRIPE_CUSTOMER_PORTAL_ID:
                    portal_params['configuration'] = django_settings.STRIPE_CUSTOMER_PORTAL_ID
                
                portal_session = stripe.billing_portal.Session.create(**portal_params)
                
                return redirect(portal_session.url)
                
            except (AttributeError, TypeError) as e:
                # Handle case where billing_portal API might not be available
                logger.error(f"Stripe billing_portal API not available: {str(e)}", exc_info=True)
                messages.error(request, _sanitize_error_message(str(e)))
                return redirect(f"{reverse('a_account:settings')}?section=subscriptions")
            except Exception as e:
                error_msg = str(e)
                # Check if it's a configuration error and retry without it
                if 'No such configuration' in error_msg or 'configuration' in error_msg.lower():
                    logger.warning(f"Stripe portal configuration invalid, trying without configuration: {error_msg}")
                    try:
                        portal_params_no_config = {
                            'customer': subscription.stripe_customer_id,
                            'return_url': return_url,
                            'locale': 'et',
                        }
                        portal_session = stripe.billing_portal.Session.create(**portal_params_no_config)
                        return redirect(portal_session.url)
                    except Exception as retry_error:
                        logger.error(f"Stripe portal error (retry failed): {str(retry_error)}", exc_info=True)
                        messages.error(request, _sanitize_error_message(str(e)))
                        return redirect(f"{reverse('a_account:settings')}?section=subscriptions")
                else:
                    logger.error(f"Stripe error: {error_msg}", exc_info=True)
                    sanitized_msg = _sanitize_error_message(error_msg)
                    messages.error(request, sanitized_msg)
                    return redirect(f"{reverse('a_account:settings')}?section=subscriptions")
        
        elif action == 'edit_portal':
            # Get current tier
            tier = get_family_subscription(family) if family else Subscription.TIER_FREE
            
            # If on FREE tier, check if they have any subscription with customer_id (even cancelled)
            if tier == Subscription.TIER_FREE:
                subscription = Subscription.objects.filter(
                    owner=user,
                    stripe_customer_id__isnull=False
                ).exclude(stripe_customer_id='').order_by('-created_at').first()
                
                if not subscription or not subscription.stripe_customer_id:
                    messages.info(request, "Stripe'i portaali kasutamiseks pead sul olema aktiivne tellimus. Vali üks pakettidest üleval.")
                    return redirect(f"{reverse('a_account:settings')}?section=subscriptions")
            else:
                # Look for active subscription
                subscription = Subscription.objects.filter(
                    owner=user,
                    tier__in=[Subscription.TIER_STARTER, Subscription.TIER_PRO],
                    stripe_customer_id__isnull=False
                ).exclude(stripe_customer_id='').first()
                
                # If not found, try any subscription with customer_id
                if not subscription:
                    subscription = Subscription.objects.filter(
                        owner=user,
                        stripe_customer_id__isnull=False
                    ).exclude(stripe_customer_id='').order_by('-created_at').first()
            
            if not subscription or not subscription.stripe_customer_id:
                messages.info(request, "Stripe'i portaali kasutamiseks pead sul olema tellimus Stripe'iga seostatud. Vali üks pakettidest üleval.")
                return redirect(f"{reverse('a_account:settings')}?section=subscriptions")
            
            if not django_settings.STRIPE_SECRET_KEY:
                messages.error(request, _sanitize_error_message(str(e)))
                return redirect(f"{reverse('a_account:settings')}?section=subscriptions")
            
            stripe.api_key = django_settings.STRIPE_SECRET_KEY
            
            try:
                # Check if billing_portal exists before accessing it
                if not hasattr(stripe, 'billing_portal'):
                    logger.error("Stripe billing_portal API not available in this Stripe SDK version")
                    messages.error(request, _sanitize_error_message(str(e)))
                    return redirect(f"{reverse('a_account:settings')}?section=subscriptions")
                
                # Build return URL - use STRIPE_BASE_URL if set, otherwise use request
                base_url = django_settings.STRIPE_BASE_URL
                if base_url:
                    # Remove trailing slash if present
                    base_url = base_url.rstrip('/')
                    return_url = f"{base_url}/account/settings/?section=subscriptions"
                else:
                    # Use request-based URL (for local development)
                    return_url = request.build_absolute_uri('/account/settings/?section=subscriptions')
                
                # Prepare portal parameters
                portal_params = {
                    'customer': subscription.stripe_customer_id,
                    'return_url': return_url,
                    'locale': 'et',
                }
                
                # Only add configuration if it's set and valid (optional parameter)
                # If configuration doesn't exist, Stripe will use default portal settings
                config_id = getattr(django_settings, 'STRIPE_CUSTOMER_PORTAL_ID', None)
                if config_id:
                    portal_params['configuration'] = config_id
                
                # Create billing portal session
                portal_session = stripe.billing_portal.Session.create(**portal_params)
                
                return redirect(portal_session.url)
                
            except (AttributeError, TypeError) as e:
                # Handle case where billing_portal API might not be available or accessed incorrectly
                logger.error(f"Stripe billing_portal API error: {str(e)}", exc_info=True)
                messages.error(request, _sanitize_error_message(str(e)))
                return redirect(f"{reverse('a_account:settings')}?section=subscriptions")
            except Exception as e:
                # Catch all Stripe errors (InvalidRequestError, etc.) and other exceptions
                error_msg = str(e)
                
                # Check if it's a configuration error
                if 'No such configuration' in error_msg or 'configuration' in error_msg.lower():
                    logger.warning(f"Stripe portal configuration invalid, trying without configuration: {error_msg}")
                    # Try again without the configuration parameter
                    try:
                        portal_params_no_config = {
                            'customer': subscription.stripe_customer_id,
                            'return_url': return_url,
                            'locale': 'et',
                        }
                        portal_session = stripe.billing_portal.Session.create(**portal_params_no_config)
                        return redirect(portal_session.url)
                    except Exception as retry_error:
                        logger.error(f"Stripe portal error (retry failed): {str(retry_error)}", exc_info=True)
                        messages.error(request, _sanitize_error_message(str(e)))
                        return redirect(f"{reverse('a_account:settings')}?section=subscriptions")
                else:
                    logger.error(f"Stripe portal error: {error_msg}", exc_info=True)
                    messages.error(request, _sanitize_error_message(str(e)))
                    return redirect(f"{reverse('a_account:settings')}?section=subscriptions")
        
        elif action == 'upgrade':
            tier = request.POST.get('tier')
            billing_period = request.POST.get('billing_period', 'monthly')
            
            if tier not in [Subscription.TIER_STARTER, Subscription.TIER_PRO]:
                messages.error(request, _sanitize_error_message(str(e)))
                return redirect(f"{reverse('a_account:settings')}?section=subscriptions")
            
            # Get appropriate price ID
            if tier == Subscription.TIER_STARTER:
                price_id = django_settings.STARTER_MONTHLY_PRICE_ID if billing_period == 'monthly' else django_settings.STARTER_YEARLY_PRICE_ID
            else:  # PRO
                price_id = django_settings.PRO_MONTHLY_PRICE_ID if billing_period == 'monthly' else django_settings.PRO_YEARLY_PRICE_ID
            
            if not django_settings.STRIPE_SECRET_KEY:
                messages.error(request, _sanitize_error_message(str(e)))
                return redirect(f"{reverse('a_account:settings')}?section=subscriptions")
            
            stripe.api_key = django_settings.STRIPE_SECRET_KEY
            
            try:
                # Get existing subscription
                existing_subscription = Subscription.objects.filter(
                    owner=user,
                    tier__in=[Subscription.TIER_STARTER, Subscription.TIER_PRO]
                ).first()
                
                # Get or create Stripe customer - check by email first to avoid duplicates
                # Note: Subscription management is only for family owners (parents) who should have email
                if not user.email:
                    messages.error(request, "Tellimuste haldamiseks peab olema e-posti aadress.")
                    return redirect(f"{reverse('a_account:settings')}?section=subscriptions")
                
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
                    except Exception as e:
                        error_msg = str(e)
                        logger.error(f"Error finding/creating customer: {error_msg}", exc_info=True)
                        messages.error(request, _sanitize_error_message(str(e)))
                        return redirect(f"{reverse('a_account:settings')}?section=subscriptions")
                else:
                    try:
                        customer = stripe.Customer.retrieve(customer_id)
                    except Exception:
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
                        
                        # Get current price ID and billing period from Stripe subscription
                        current_price_id = stripe_subscription['items']['data'][0]['price']['id']
                        current_billing_period = _get_billing_period_from_price_id(current_price_id)
                        
                        # Validate billing period change if switching
                        if current_billing_period and billing_period != current_billing_period:
                            # User is changing billing period (monthly <-> yearly)
                            # This is allowed - Stripe will handle proration correctly
                            logger.info(f"User {user.id} changing billing period from {current_billing_period} to {billing_period}")
                        
                        # Get the current subscription item ID
                        subscription_item_id = stripe_subscription['items']['data'][0]['id']
                        
                        # Verify the new price ID is valid
                        new_price_tier = get_tier_from_price_id(price_id)
                        if not new_price_tier or new_price_tier != tier:
                            logger.error(f"Price ID {price_id} does not match tier {tier}")
                            messages.error(request, _sanitize_error_message(str(e)))
                            return redirect(f"{reverse('a_account:settings')}?section=subscriptions")
                        
                        # Update subscription with new price (prorated)
                        # Stripe will automatically handle proration when changing between monthly/yearly
                        updated_subscription = stripe.Subscription.modify(
                            existing_subscription.stripe_subscription_id,
                            items=[{
                                'id': subscription_item_id,
                                'price': price_id,
                            }],
                            proration_behavior='create_prorations',  # Always prorate when changing plans
                            metadata={
                                'user_id': str(user.id),
                                'family_id': str(family.id),
                                'tier': tier,
                            }
                        )
                        
                        # Update local subscription record
                        existing_subscription.tier = tier
                        existing_subscription.status = updated_subscription.status
                        
                        # Safely update period dates from Stripe subscription object
                        # These are optional fields, so we catch any errors and continue
                        try:
                            period_start = getattr(updated_subscription, 'current_period_start', None)
                            if period_start:
                                existing_subscription.current_period_start = timezone.make_aware(
                                    datetime.fromtimestamp(int(period_start))
                                )
                        except Exception as e:
                            logger.warning(f"Could not update current_period_start: {str(e)}")
                            # Continue without updating period start - not critical for subscription
                        
                        try:
                            period_end = getattr(updated_subscription, 'current_period_end', None)
                            if period_end:
                                existing_subscription.current_period_end = timezone.make_aware(
                                    datetime.fromtimestamp(int(period_end))
                                )
                        except Exception as e:
                            logger.warning(f"Could not update current_period_end: {str(e)}")
                            # Continue without updating period end - not critical for subscription
                        
                        existing_subscription.save()
                        
                        messages.success(request, f"Pakett uuendati tasemele {existing_subscription.get_tier_display()}! Maksed on proportsionaalsed.")
                        return redirect(f"{reverse('a_account:settings')}?section=subscriptions")
                        
                    except Exception as e:
                        error_msg = str(e) or repr(e)
                        error_type = type(e).__name__
                        logger.error(f"Stripe subscription update error ({error_type}): {error_msg}", exc_info=True)
                        
                        # Sanitize error message before showing to user
                        sanitized_msg = _sanitize_error_message(error_msg)
                        messages.error(request, sanitized_msg)
                        return redirect(f"{reverse('a_account:settings')}?section=subscriptions")
                
                # No active subscription - create new one via checkout
                # Build URLs - use STRIPE_BASE_URL if set, otherwise use request
                base_url = django_settings.STRIPE_BASE_URL
                if base_url:
                    # Remove trailing slash if present
                    base_url = base_url.rstrip('/')
                    success_url = f"{base_url}/subscription/success/?session_id={{CHECKOUT_SESSION_ID}}"
                    cancel_url = f"{base_url}/account/settings/?section=subscriptions"
                    return_url = f"{base_url}/account/settings/?section=subscriptions"
                else:
                    # Use request-based URLs (for local development)
                    success_url = request.build_absolute_uri('/subscription/success/') + '?session_id={CHECKOUT_SESSION_ID}'
                    cancel_url = request.build_absolute_uri('/account/settings/?section=subscriptions')
                    return_url = request.build_absolute_uri('/account/settings/?section=subscriptions')
                
                # Apply promo code automatically for new subscriptions (let Stripe enforce one-time usage)
                discounts = []
                promo_code = None
                # Only apply if no existing active paid subscription
                had_paid_subscription = Subscription.objects.filter(
                    owner=user,
                    tier__in=[Subscription.TIER_STARTER, Subscription.TIER_PRO]
                ).exists()
                if not had_paid_subscription:
                    promo_code = _get_promo_code_for_tier(tier)
                    if promo_code:
                        discounts = [{'promotion_code': promo_code}]
                
                checkout_params = {
                    'customer': customer_id,
                    'payment_method_types': ['card'],
                    'line_items': [{
                        'price': price_id,
                        'quantity': 1,
                    }],
                    'mode': 'subscription',
                    'success_url': success_url,
                    'cancel_url': cancel_url,
                    'locale': 'et',
                    'metadata': {
                        'user_id': str(user.id),
                        'family_id': str(family.id),
                        'tier': tier,
                        'applied_promo_code': promo_code or '',
                    }
                }
                
                # Only add discounts if we have a promo code, otherwise allow manual promotion codes
                if discounts:
                    checkout_params['discounts'] = discounts
                else:
                    checkout_params['allow_promotion_codes'] = True
                
                checkout_session = stripe.checkout.Session.create(**checkout_params)
                
                return redirect(checkout_session.url)
                
            except Exception as e:
                error_msg = str(e)
                logger.error(f"Stripe error: {error_msg}", exc_info=True)
                sanitized_msg = _sanitize_error_message(error_msg)
                messages.error(request, sanitized_msg)
                return redirect(f"{reverse('a_account:settings')}?section=subscriptions")

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
        "has_email": bool(user.email),
    }
    return render(request, 'a_account/subscriptions.html', context)


@login_required
def delete_account(request):
    """Delete user account - only for parents"""
    user = request.user
    
    # Prevent children from deleting their accounts
    if user.role == User.ROLE_CHILD:
        messages.error(request, "Lapsed ei saa oma kontot kustutada.")
        return redirect(f"{reverse('a_account:settings')}?section=general")
    
    if request.method != 'POST':
        messages.error(request, f"Midagi läks valesti. Kui probleem püsib, palun võta ühendust tugiteenusega: {django_settings.SUPPORT_EMAIL}")
        return redirect(f"{reverse('a_account:settings')}?section=general")
    delete_children_choice = request.POST.get('delete_children', 'delete')
    if delete_children_choice not in ('delete', 'keep'):
        delete_children_choice = 'delete'

    # Get family before deleting user
    family = _get_family_for_user(user)
    is_family_owner = family and family.owner == user if family else False
    
    # Check for active subscription if user is owner
    if is_family_owner:
        active_subscription = Subscription.objects.filter(
            owner=user,
            tier__in=[Subscription.TIER_STARTER, Subscription.TIER_PRO]
        ).first()
        
        if active_subscription and active_subscription.is_active():
            messages.error(request, "Enne konto kustutamist pead tühistama aktiivse tellimuse. Palun mine tellimuste seadistustesse ja tühista tellimus.")
            return redirect(f"{reverse('a_account:settings')}?section=subscriptions")
    
    # Handle family owner deletion
    if family and is_family_owner:
        child_accounts = list(family.members.filter(role=User.ROLE_CHILD))
        if delete_children_choice == 'delete':
            for child in child_accounts:
                try:
                    from allauth.account.models import EmailAddress
                    EmailAddress.objects.filter(user=child).delete()
                except Exception:
                    pass
                child.delete()
        else:
            for child in child_accounts:
                family.members.remove(child)
        
        # Delete subscriptions
        try:
            subscriptions = Subscription.objects.filter(owner=user)
            for subscription in subscriptions:
                subscription.delete()
        except Exception:
            pass
        
        # Remove all members from family
        family.members.clear()
        
        # Delete the family (this will CASCADE delete tasks)
        family.delete()
    elif family:
        # Remove user from family if they're a member
            family.members.remove(user)
    
    # Delete EmailAddress records
    try:
        from allauth.account.models import EmailAddress
        EmailAddress.objects.filter(user=user).delete()
    except Exception:
        pass
    
    # Logout user before deleting
    from django.contrib.auth import logout
    logout(request)
    
    # Delete user account
    user.delete()
    
    messages.success(request, "Konto kustutatud edukalt.")
    return redirect('a_landing:landing_index')

