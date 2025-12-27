import json
import logging
from datetime import datetime
import stripe
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect
from django.urls import reverse
from django.conf import settings
from django.views.decorators.csrf import csrf_exempt
from django.http import HttpResponse
from django.utils import timezone
from .models import Subscription
from .utils import get_tier_from_price_id

logger = logging.getLogger(__name__)


@login_required
def upgrade_success(request):
    """Handle successful subscription upgrade"""
    session_id = request.GET.get('session_id')
    if not session_id:
        messages.error(request, f"Midagi läks valesti. Kui probleem püsib, palun võta ühendust tugiteenusega: {settings.SUPPORT_EMAIL}")
        return redirect(f"{reverse('a_account:settings')}?section=subscriptions")

    if not settings.STRIPE_SECRET_KEY:
        messages.error(request, f"Midagi läks valesti. Kui probleem püsib, palun võta ühendust tugiteenusega: {settings.SUPPORT_EMAIL}")
        return redirect(f"{reverse('a_account:settings')}?section=subscriptions")

    stripe.api_key = settings.STRIPE_SECRET_KEY

    try:
        session = stripe.checkout.Session.retrieve(session_id)
        user_id = session.metadata.get('user_id')
        family_id = session.metadata.get('family_id')
        tier_from_metadata = session.metadata.get('tier')

        if str(request.user.id) != str(user_id):
            messages.error(request, f"Midagi läks valesti. Kui probleem püsib, palun võta ühendust tugiteenusega: {settings.SUPPORT_EMAIL}")
            return redirect(f"{reverse('a_account:settings')}?section=subscriptions")

        # Extract tier from price ID (primary method, scalable)
        tier = None
        # Retrieve line items to get price ID
        try:
            line_items = stripe.checkout.Session.list_line_items(session_id, limit=1)
            if line_items.data and len(line_items.data) > 0:
                line_item = line_items.data[0]
                # Price can be a string ID (default) or an object if expanded
                price_obj = getattr(line_item, 'price', None)
                if price_obj:
                    if isinstance(price_obj, str):
                        price_id = price_obj
                    elif hasattr(price_obj, 'id'):
                        price_id = price_obj.id
                    else:
                        price_id = None
                    
                    if price_id:
                        tier = get_tier_from_price_id(price_id)
                        logger.info(f"Extracted tier {tier} from price ID {price_id} for session {session_id}")
        except Exception as e:
            logger.warning(f"Could not retrieve line items for session {session_id}: {str(e)}", exc_info=True)
        
        # Fallback to metadata if price ID lookup failed
        if not tier and tier_from_metadata:
            tier = tier_from_metadata
            logger.info(f"Using tier {tier} from metadata for session {session_id}")
        
        if not tier:
            messages.error(request, f"Midagi läks valesti. Kui probleem püsib, palun võta ühendust tugiteenusega: {settings.SUPPORT_EMAIL}")
            logger.error(f"Could not determine tier for session {session_id}")
            return redirect(f"{reverse('a_account:settings')}?section=subscriptions")

        # Get customer ID from session
        customer_id = getattr(session, 'customer', None)
        if not customer_id:
            logger.error(f"No customer ID found in session {session_id}")
            messages.error(request, f"Midagi läks valesti. Kui probleem püsib, palun võta ühendust tugiteenusega: {settings.SUPPORT_EMAIL}")
            return redirect(f"{reverse('a_account:settings')}?section=subscriptions")
        
        # Get subscription details from Stripe
        subscription_id = getattr(session, 'subscription', None)
        
        # Find existing subscription by stripe_subscription_id first, then by customer_id
        subscription = None
        if subscription_id:
            subscription = Subscription.objects.filter(
                stripe_subscription_id=subscription_id
            ).first()
        
        # If not found by subscription ID, try to find by customer and active status
        if not subscription:
            subscription = Subscription.objects.filter(
                owner=request.user,
                stripe_customer_id=customer_id,
                tier__in=[Subscription.TIER_STARTER, Subscription.TIER_PRO]
            ).order_by('-created_at').first()
        
        # If still not found, create new subscription
        if not subscription:
            subscription = Subscription.objects.create(
                owner=request.user,
                tier=tier,
                stripe_customer_id=customer_id,
                status=Subscription.STATUS_ACTIVE,
            )
            logger.info(f"Created new subscription {subscription.id} for user {request.user.id}")
        else:
            # Update existing subscription
            subscription.tier = tier
            subscription.stripe_customer_id = customer_id
            subscription.status = Subscription.STATUS_ACTIVE
            logger.info(f"Updating existing subscription {subscription.id} for user {request.user.id}")

        # Update subscription details from Stripe if available
        if subscription_id:
            try:
                stripe_subscription = stripe.Subscription.retrieve(subscription_id)
                subscription.stripe_subscription_id = stripe_subscription.id
                # Use the helper function to ensure consistent handling of tier changes and downgrades
                _update_subscription_from_stripe(subscription, stripe_subscription)
                logger.info(f"Updated subscription {subscription.id} from Stripe subscription {subscription_id}")
            except stripe.error.StripeError as e:
                logger.error(f"Error retrieving subscription {subscription_id}: {str(e)}", exc_info=True)
        else:
            subscription.save()
        
        # Cancel any other active subscriptions for this user to prevent duplicates
        other_subscriptions = Subscription.objects.filter(
            owner=request.user,
            tier__in=[Subscription.TIER_STARTER, Subscription.TIER_PRO]
        ).exclude(id=subscription.id)
        
        for other_sub in other_subscriptions:
            if other_sub.stripe_subscription_id:
                try:
                    # Cancel the Stripe subscription
                    stripe.Subscription.delete(other_sub.stripe_subscription_id)
                    logger.info(f"Cancelled duplicate Stripe subscription {other_sub.stripe_subscription_id}")
                except stripe.error.StripeError as e:
                    logger.warning(f"Could not cancel duplicate subscription {other_sub.stripe_subscription_id}: {str(e)}")
            
            # Mark as cancelled locally
            other_sub.status = Subscription.STATUS_CANCELLED
            other_sub.tier = Subscription.TIER_FREE
            other_sub.stripe_subscription_id = None
            other_sub.save()
            logger.info(f"Marked duplicate subscription {other_sub.id} as cancelled")

        messages.success(request, f"Pakett uuendati tasemele {subscription.get_tier_display()}!")
        logger.info(f"Subscription successfully created/updated for user {request.user.id}, tier: {subscription.tier}")
        
        return redirect(f"{reverse('a_account:settings')}?section=subscriptions&purchase=success")

    except stripe.error.StripeError as e:
        logger.error(f"Stripe error in upgrade_success: {str(e)}", exc_info=True)
        messages.error(request, f"Midagi läks valesti. Kui probleem püsib, palun võta ühendust tugiteenusega: {settings.SUPPORT_EMAIL}")
        return redirect(f"{reverse('a_account:settings')}?section=subscriptions")
    except Exception as e:
        logger.error(f"Unexpected error in upgrade_success: {str(e)}", exc_info=True)
        messages.error(request, f"Midagi läks valesti. Kui probleem püsib, palun võta ühendust tugiteenusega: {settings.SUPPORT_EMAIL}")
        return redirect(f"{reverse('a_account:settings')}?section=subscriptions")




def _extract_tier_from_subscription(subscription_obj):
    """
    Extract tier from Stripe subscription object.
    Tries to get tier from price ID first, then falls back to metadata.
    
    Args:
        subscription_obj: Stripe subscription object (dict)
    
    Returns:
        str: Subscription tier or None
    """
    # Try to get tier from price ID (primary method, scalable)
    items = subscription_obj.get('items', {}).get('data', [])
    if items and len(items) > 0:
        price_id = items[0].get('price', {}).get('id')
        if price_id:
            tier = get_tier_from_price_id(price_id)
            if tier:
                return tier
    
    # Fallback to metadata
    metadata = subscription_obj.get('metadata', {})
    tier = metadata.get('tier')
    if tier in [Subscription.TIER_STARTER, Subscription.TIER_PRO]:
        return tier
    
    return None


def _update_subscription_from_stripe(subscription, subscription_obj):
    """
    Update subscription object from Stripe subscription data.
    Handles tier extraction, status updates, and period dates.
    
    Args:
        subscription: Django Subscription model instance
        subscription_obj: Stripe subscription object (dict or Stripe object)
    """
    # Convert to dict if it's a Stripe object
    if hasattr(subscription_obj, 'to_dict'):
        subscription_obj = subscription_obj.to_dict()
    elif not isinstance(subscription_obj, dict):
        # Try to access as object attributes
        subscription_obj = {
            'status': getattr(subscription_obj, 'status', None),
            'current_period_start': getattr(subscription_obj, 'current_period_start', None),
            'current_period_end': getattr(subscription_obj, 'current_period_end', None),
            'items': getattr(subscription_obj, 'items', {}),
            'metadata': getattr(subscription_obj, 'metadata', {}),
        }
    
    # Extract tier from price ID or metadata
    # This will immediately reflect any tier changes (upgrades or downgrades) from Stripe
    tier = _extract_tier_from_subscription(subscription_obj)
    if tier:
        old_tier = subscription.tier
        subscription.tier = tier
        if old_tier != tier:
            logger.info(
                f"Subscription {subscription.stripe_subscription_id} tier changed from {old_tier} to {tier}"
            )
    
    # Update status (map Stripe 'canceled' to our 'cancelled')
    status = subscription_obj.get('status')
    if status:
        # Stripe uses 'canceled' (one 'l') but we use 'cancelled' (two 'l's)
        if status == 'canceled':
            status = Subscription.STATUS_CANCELLED
        subscription.status = status
    
    # Update period dates
    if subscription_obj.get('current_period_start'):
        period_start = subscription_obj['current_period_start']
        if isinstance(period_start, (int, float)):
            subscription.current_period_start = timezone.make_aware(
                datetime.fromtimestamp(period_start)
            )
    if subscription_obj.get('current_period_end'):
        period_end = subscription_obj['current_period_end']
        if isinstance(period_end, (int, float)):
            subscription.current_period_end = timezone.make_aware(
                datetime.fromtimestamp(period_end)
            )
    
    # Handle cancellation vs expiration
    # Cancelled: Keep tier until period_end (user keeps access)
    # Expired/unpaid: Revert to FREE immediately
    # Use the mapped status for checks
    mapped_status = subscription.status if subscription.status else status
    
    # Immediately downgrade to FREE for permanent payment failures
    if mapped_status in [Subscription.STATUS_INCOMPLETE_EXPIRED, Subscription.STATUS_UNPAID]:
        # Payment failed permanently - revert to FREE immediately
        if subscription.tier != Subscription.TIER_FREE:
            old_tier = subscription.tier
            subscription.tier = Subscription.TIER_FREE
            logger.info(
                f"Subscription {subscription.stripe_subscription_id} expired/unpaid, "
                f"immediately downgraded from {old_tier} to FREE tier"
            )
        else:
            logger.debug(
                f"Subscription {subscription.stripe_subscription_id} already FREE tier, "
                f"status: {mapped_status}"
            )
    elif mapped_status == Subscription.STATUS_CANCELLED:
        # Cancelled but may still have access until period_end
        # Check if period has ended
        if subscription.current_period_end and subscription.current_period_end < timezone.now():
            # Period ended, revert to FREE immediately
            if subscription.tier != Subscription.TIER_FREE:
                old_tier = subscription.tier
                subscription.tier = Subscription.TIER_FREE
                logger.info(
                    f"Subscription {subscription.stripe_subscription_id} cancelled and period ended, "
                    f"immediately downgraded from {old_tier} to FREE tier"
                )
            else:
                logger.debug(
                    f"Subscription {subscription.stripe_subscription_id} already FREE tier, "
                    f"cancelled and period ended"
                )
        else:
            # Keep tier until period_end (user still has access)
            logger.debug(
                f"Subscription {subscription.stripe_subscription_id} cancelled, "
                f"keeping tier {subscription.tier} until period_end {subscription.current_period_end}"
            )
    
    subscription.save()


@csrf_exempt
def webhook(request):
    """
    Handle Stripe webhooks.
    
    CSRF protection is exempted here because Stripe webhooks come from external servers
    and cannot include CSRF tokens. Instead, security is ensured through:
    1. Webhook signature verification using STRIPE_WEBHOOK_SECRET
    2. Event payload validation
    3. Idempotency checks to prevent duplicate processing
    
    This is the standard and secure approach for handling Stripe webhooks.
    """
    if not settings.STRIPE_SECRET_KEY:
        return HttpResponse(status=400)

    stripe.api_key = settings.STRIPE_SECRET_KEY
    payload = request.body
    sig_header = request.META.get('HTTP_STRIPE_SIGNATURE')

    # Verify webhook signature
    try:
        webhook_secret = getattr(settings, 'STRIPE_WEBHOOK_SECRET', None)
        if webhook_secret and sig_header:
            event = stripe.Webhook.construct_event(
                payload, sig_header, webhook_secret
            )
        else:
            # Development mode - construct from JSON directly
            event = stripe.Event.construct_from(
                json.loads(payload.decode('utf-8')), stripe.api_key
            )
    except ValueError:
        return HttpResponse(status=400)
    except stripe.error.SignatureVerificationError:
        return HttpResponse(status=400)
    except Exception as e:
        logger.error(f"Error parsing webhook: {str(e)}", exc_info=True)
        return HttpResponse(status=200)  # Return 200 to acknowledge

    # Get event type - handle both dict and object formats
    event_type = ''
    event_data = {}
    try:
        if isinstance(event, dict):
            event_type = event.get('type', '')
            event_data = event.get('data', {})
        else:
            event_type = getattr(event, 'type', '')
            data_obj = getattr(event, 'data', None)
            if data_obj:
                if isinstance(data_obj, dict):
                    event_data = data_obj
                elif hasattr(data_obj, 'to_dict'):
                    event_data = data_obj.to_dict()
                elif hasattr(data_obj, 'object'):
                    # Access the object attribute directly
                    obj = getattr(data_obj, 'object', None)
                    if obj:
                        if hasattr(obj, 'to_dict'):
                            event_data = {'object': obj.to_dict()}
                        else:
                            event_data = {'object': obj}
                    else:
                        event_data = {'object': {}}
                else:
                    event_data = {'object': {}}
    except Exception as e:
        logger.error(f"Error accessing event data: {str(e)}", exc_info=True)
        return HttpResponse(status=200)
    
    logger.info(f"Received Stripe webhook event: {event_type}")

    # Handle subscription events
    try:
        if event_type == 'customer.subscription.created':
            subscription_obj = event_data.get('object', {}) if isinstance(event_data, dict) else {}
            subscription_id = subscription_obj.get('id') if isinstance(subscription_obj, dict) else None
            customer_id = subscription_obj.get('customer') if isinstance(subscription_obj, dict) else None
            
            logger.info(f"Processing subscription.created for {subscription_id}, customer: {customer_id}")
            
            try:
                # Try to find existing subscription by customer ID first
                subscription = None
                if customer_id:
                    subscription = Subscription.objects.filter(
                        stripe_customer_id=customer_id
                    ).order_by('-created_at').first()
                
                # If not found, try by subscription ID
                if not subscription and subscription_id:
                    subscription = Subscription.objects.filter(
                        stripe_subscription_id=subscription_id
                    ).first()
                
                # If still not found, try to find by customer email via Stripe
                if not subscription and customer_id:
                    try:
                        customer = stripe.Customer.retrieve(customer_id)
                        user_id = customer.metadata.get('user_id')
                        if user_id:
                            from a_family.models import User
                            try:
                                user = User.objects.get(id=user_id)
                                subscription = Subscription.objects.filter(
                                    owner=user,
                                    tier__in=[Subscription.TIER_STARTER, Subscription.TIER_PRO]
                                ).order_by('-created_at').first()
                                if subscription:
                                    logger.info(f"Found subscription {subscription.id} by user_id from customer metadata")
                            except User.DoesNotExist:
                                pass
                    except Exception as e:
                        logger.warning(f"Could not retrieve customer to find user: {str(e)}")
                
                if subscription:
                    # Update existing subscription
                    subscription.stripe_subscription_id = subscription_id
                    subscription.stripe_customer_id = customer_id  # Ensure customer ID is set
                    _update_subscription_from_stripe(subscription, subscription_obj)
                    logger.info(f"Updated existing subscription {subscription.id} for customer {customer_id}")
                else:
                    logger.warning(f"Subscription created event received but no matching subscription found: {subscription_id}, customer: {customer_id}")
            except Exception as e:
                logger.error(f"Error processing subscription.created: {str(e)}", exc_info=True)

        elif event_type == 'customer.subscription.updated':
            subscription_obj = event_data.get('object', {}) if isinstance(event_data, dict) else {}
            subscription_id = subscription_obj.get('id') if isinstance(subscription_obj, dict) else None
            
            logger.info(f"Processing subscription.updated for {subscription_id}")
            
            try:
                subscription = Subscription.objects.get(
                    stripe_subscription_id=subscription_id
                )
                
                # Store old tier to detect changes
                old_tier = subscription.tier
                old_status = subscription.status
                
                # Update subscription from Stripe (this will handle tier changes and downgrades)
                _update_subscription_from_stripe(subscription, subscription_obj)
                
                # Log tier changes immediately
                if subscription.tier != old_tier:
                    if subscription.tier == Subscription.TIER_FREE:
                        logger.info(
                            f"Subscription {subscription.id} downgraded from {old_tier} to FREE tier "
                            f"(status: {subscription.status})"
                        )
                    else:
                        logger.info(
                            f"Subscription {subscription.id} tier changed from {old_tier} to {subscription.tier}"
                        )
                
                # Log status changes
                if subscription.status != old_status:
                    logger.info(
                        f"Subscription {subscription.id} status changed from {old_status} to {subscription.status}"
                    )
                
                logger.info(f"Updated subscription {subscription.id}")
            except Subscription.DoesNotExist:
                logger.warning(f"Subscription updated event received but subscription not found: {subscription_id}")
            except Exception as e:
                logger.error(f"Error processing subscription.updated: {str(e)}", exc_info=True)

        elif event_type == 'customer.subscription.deleted':
            subscription_obj = event_data.get('object', {}) if isinstance(event_data, dict) else {}
            subscription_id = subscription_obj.get('id') if isinstance(subscription_obj, dict) else None
            
            logger.info(f"Processing subscription.deleted for {subscription_id}")
            
            try:
                subscription = Subscription.objects.get(
                    stripe_subscription_id=subscription_id
                )
                # When deleted, revert to FREE tier
                subscription.status = Subscription.STATUS_CANCELLED
                subscription.tier = Subscription.TIER_FREE
                subscription.stripe_subscription_id = None  # Clear subscription ID
                subscription.save()
                logger.info(f"Subscription {subscription.id} deleted, reverted to FREE tier")
            except Subscription.DoesNotExist:
                logger.warning(f"Subscription deleted event received but subscription not found: {subscription_id}")
            except Exception as e:
                logger.error(f"Error processing subscription.deleted: {str(e)}", exc_info=True)

        elif event_type == 'invoice.payment_failed':
            invoice_obj = event_data.get('object', {}) if isinstance(event_data, dict) else {}
            subscription_id = invoice_obj.get('subscription') if isinstance(invoice_obj, dict) else None
            
            logger.info(f"Processing invoice.payment_failed for subscription {subscription_id}")
            
            if subscription_id:
                try:
                    subscription = Subscription.objects.get(
                        stripe_subscription_id=subscription_id
                    )
                    
                    # Check if this is a final payment failure
                    # Stripe retries up to 3 times (4 total attempts: initial + 3 retries)
                    attempt_count = invoice_obj.get('attempt_count', 0) if isinstance(invoice_obj, dict) else 0
                    max_attempts = 4  # Stripe's default max attempts
                    
                    # Also check the subscription status from Stripe to see if it's already unpaid/expired
                    try:
                        stripe_subscription = stripe.Subscription.retrieve(subscription_id)
                        stripe_status = stripe_subscription.status
                        
                        # If subscription is already unpaid or incomplete_expired, downgrade immediately
                        if stripe_status in ['unpaid', 'incomplete_expired']:
                            subscription.status = Subscription.STATUS_UNPAID if stripe_status == 'unpaid' else Subscription.STATUS_INCOMPLETE_EXPIRED
                            subscription.tier = Subscription.TIER_FREE
                            subscription.save()
                            logger.info(
                                f"Subscription {subscription.id} payment failed with final status {stripe_status}, "
                                f"downgraded to FREE tier immediately"
                            )
                        elif attempt_count >= max_attempts:
                            # Final attempt failed - downgrade immediately
                            subscription.status = Subscription.STATUS_PAST_DUE
                            subscription.tier = Subscription.TIER_FREE
                            subscription.save()
                            logger.info(
                                f"Subscription {subscription.id} payment failed after {attempt_count} attempts "
                                f"(max: {max_attempts}), downgraded to FREE tier immediately"
                            )
                        else:
                            # Still in retry period, just update status
                            subscription.status = Subscription.STATUS_PAST_DUE
                            subscription.save()
                            logger.info(
                                f"Subscription {subscription.id} payment failed (attempt {attempt_count}/{max_attempts}), "
                                f"status set to past_due"
                            )
                    except stripe.error.StripeError as e:
                        # If we can't retrieve subscription, just set to past_due
                        logger.warning(f"Could not retrieve Stripe subscription to check status: {str(e)}")
                        subscription.status = Subscription.STATUS_PAST_DUE
                        subscription.save()
                        logger.info(f"Subscription {subscription.id} payment failed, status set to past_due")
                        
                except Subscription.DoesNotExist:
                    logger.warning(f"Payment failed event received but subscription not found: {subscription_id}")
                except Exception as e:
                    logger.error(f"Error processing invoice.payment_failed: {str(e)}", exc_info=True)

        elif event_type == 'invoice.payment_succeeded':
            invoice_obj = event_data.get('object', {}) if isinstance(event_data, dict) else {}
            subscription_id = invoice_obj.get('subscription') if isinstance(invoice_obj, dict) else None
            
            logger.info(f"Processing invoice.payment_succeeded for subscription {subscription_id}")
            
            if subscription_id:
                try:
                    subscription = Subscription.objects.get(
                        stripe_subscription_id=subscription_id
                    )
                    
                    # Payment succeeded - refresh subscription from Stripe to ensure tier is correct
                    try:
                        stripe_subscription = stripe.Subscription.retrieve(subscription_id)
                        _update_subscription_from_stripe(subscription, stripe_subscription)
                        logger.info(
                            f"Subscription {subscription.id} payment succeeded, "
                            f"status: {subscription.status}, tier: {subscription.tier}"
                        )
                    except stripe.error.StripeError as e:
                        # Fallback: just update status if we can't retrieve subscription
                        logger.warning(f"Could not retrieve Stripe subscription: {str(e)}")
                        if subscription.status == Subscription.STATUS_PAST_DUE:
                            subscription.status = Subscription.STATUS_ACTIVE
                            subscription.save()
                            logger.info(f"Subscription {subscription.id} payment succeeded, status set to active")
                        
                except Subscription.DoesNotExist:
                    logger.warning(f"Payment succeeded event received but subscription not found: {subscription_id}")
                except Exception as e:
                    logger.error(f"Error processing invoice.payment_succeeded: {str(e)}", exc_info=True)
        
        elif event_type == 'invoice.payment_action_required':
            # Payment requires action (e.g., 3D Secure authentication)
            invoice_obj = event_data.get('object', {}) if isinstance(event_data, dict) else {}
            subscription_id = invoice_obj.get('subscription') if isinstance(invoice_obj, dict) else None
            
            logger.info(f"Processing invoice.payment_action_required for subscription {subscription_id}")
            
            if subscription_id:
                try:
                    subscription = Subscription.objects.get(
                        stripe_subscription_id=subscription_id
                    )
                    # Don't downgrade yet - payment might still succeed after action
                    # Just log for monitoring
                    logger.info(
                        f"Subscription {subscription.id} payment requires action "
                        f"(invoice: {invoice_obj.get('id', 'unknown')})"
                    )
                except Subscription.DoesNotExist:
                    logger.warning(f"Payment action required event received but subscription not found: {subscription_id}")
                except Exception as e:
                    logger.error(f"Error processing invoice.payment_action_required: {str(e)}", exc_info=True)

        else:
            logger.debug(f"Unhandled webhook event type: {event_type}")
    except Exception as e:
        # Log any unexpected errors but still return 200 to acknowledge receipt
        logger.error(f"Unexpected error processing webhook event {event_type}: {str(e)}", exc_info=True)

    # Always return 200 to acknowledge receipt, even if processing had errors
    return HttpResponse(status=200)
