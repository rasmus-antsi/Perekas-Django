"""
Nightly subscription sync command.
Syncs all subscriptions with Stripe to ensure plan correctness.
Downgrades subscriptions if payments have failed or haven't been paid.
"""
import logging
import stripe
from django.core.management.base import BaseCommand
from django.conf import settings
from django.utils import timezone
from datetime import datetime
from a_subscription.models import Subscription
from a_subscription.views import _update_subscription_from_stripe, _extract_tier_from_subscription

logger = logging.getLogger(__name__)


def _map_stripe_status_to_django(stripe_status):
    """
    Map Stripe subscription status to Django subscription status.
    Stripe uses 'canceled' (one 'l') but Django uses 'cancelled' (two 'l's).
    """
    status_mapping = {
        'active': Subscription.STATUS_ACTIVE,
        'canceled': Subscription.STATUS_CANCELLED,  # Stripe uses 'canceled', we use 'cancelled'
        'cancelled': Subscription.STATUS_CANCELLED,  # Handle both just in case
        'past_due': Subscription.STATUS_PAST_DUE,
        'incomplete': Subscription.STATUS_INCOMPLETE,
        'incomplete_expired': Subscription.STATUS_INCOMPLETE_EXPIRED,
        'trialing': Subscription.STATUS_TRIALING,
        'unpaid': Subscription.STATUS_UNPAID,
    }
    return status_mapping.get(stripe_status, stripe_status)


class Command(BaseCommand):
    help = 'Syncs all subscriptions with Stripe and downgrades if payments failed'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Perform a dry run without actually making changes.',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        
        if not settings.STRIPE_SECRET_KEY:
            self.stdout.write(
                self.style.WARNING('STRIPE_SECRET_KEY not set, skipping subscription sync')
            )
            return
        
        stripe.api_key = settings.STRIPE_SECRET_KEY
        
        # Get all non-free subscriptions
        subscriptions = Subscription.objects.filter(
            tier__in=[Subscription.TIER_STARTER, Subscription.TIER_PRO]
        ).select_related('owner')
        
        total_count = subscriptions.count()
        synced_count = 0
        downgraded_count = 0
        error_count = 0
        
        self.stdout.write(f"Found {total_count} subscription(s) to sync...")
        
        for subscription in subscriptions:
            try:
                # Skip if no Stripe subscription ID
                if not subscription.stripe_subscription_id:
                    if dry_run:
                        self.stdout.write(
                            f"DRY RUN: Subscription {subscription.id} has no stripe_subscription_id, "
                            f"would check by customer_id or downgrade to FREE"
                        )
                    else:
                        # If subscription has customer_id, try to find active subscription in Stripe
                        if subscription.stripe_customer_id:
                            try:
                                # List all subscriptions for this customer
                                stripe_subscriptions = stripe.Subscription.list(
                                    customer=subscription.stripe_customer_id,
                                    status='all',
                                    limit=10
                                )
                                
                                # Find active subscription
                                active_stripe_sub = None
                                for sub in stripe_subscriptions.data:
                                    if sub.status in ['active', 'trialing']:
                                        active_stripe_sub = sub
                                        break
                                
                                if active_stripe_sub:
                                    # Found active subscription, update our record
                                    subscription.stripe_subscription_id = active_stripe_sub.id
                                    _update_subscription_from_stripe(subscription, active_stripe_sub)
                                    subscription.save()
                                    synced_count += 1
                                    logger.info(
                                        f"Found and synced Stripe subscription {active_stripe_sub.id} "
                                        f"for subscription {subscription.id}"
                                    )
                                else:
                                    # No active subscription found, downgrade to FREE
                                    subscription.tier = Subscription.TIER_FREE
                                    subscription.status = Subscription.STATUS_CANCELLED
                                    subscription.save()
                                    downgraded_count += 1
                                    logger.info(
                                        f"No active Stripe subscription found for subscription {subscription.id}, "
                                        f"downgraded to FREE"
                                    )
                            except stripe.error.StripeError as e:
                                logger.error(
                                    f"Error checking Stripe for subscription {subscription.id}: {str(e)}"
                                )
                                error_count += 1
                        else:
                            # No customer_id either, downgrade to FREE
                            subscription.tier = Subscription.TIER_FREE
                            subscription.status = Subscription.STATUS_CANCELLED
                            subscription.save()
                            downgraded_count += 1
                            logger.info(
                                f"Subscription {subscription.id} has no Stripe IDs, downgraded to FREE"
                            )
                    continue
                
                # Retrieve subscription from Stripe
                try:
                    stripe_subscription = stripe.Subscription.retrieve(subscription.stripe_subscription_id)
                except stripe.error.StripeError as e:
                    if 'No such subscription' in str(e):
                        # Subscription doesn't exist in Stripe, downgrade to FREE
                        if dry_run:
                            self.stdout.write(
                                f"DRY RUN: Subscription {subscription.id} not found in Stripe, "
                                f"would downgrade to FREE"
                            )
                        else:
                            subscription.tier = Subscription.TIER_FREE
                            subscription.status = Subscription.STATUS_CANCELLED
                            subscription.stripe_subscription_id = None
                            subscription.save()
                            downgraded_count += 1
                            logger.info(
                                f"Subscription {subscription.id} not found in Stripe, downgraded to FREE"
                            )
                    else:
                        logger.error(
                            f"Error retrieving Stripe subscription {subscription.stripe_subscription_id}: {str(e)}"
                        )
                        error_count += 1
                    continue
                
                # Check subscription status
                stripe_status = stripe_subscription.status
                django_status = _map_stripe_status_to_django(stripe_status)
                
                # Update subscription from Stripe data
                if dry_run:
                    # Extract tier from Stripe
                    tier_from_stripe = _extract_tier_from_subscription(stripe_subscription)
                    current_tier = subscription.tier
                    
                    self.stdout.write(
                        f"DRY RUN: Subscription {subscription.id} (owner: {subscription.owner.get_display_name()}):\n"
                        f"  Current tier: {current_tier}\n"
                        f"  Stripe tier: {tier_from_stripe or 'unknown'}\n"
                        f"  Stripe status: {stripe_status}\n"
                        f"  Would sync and update if needed"
                    )
                    
                    # Check if should downgrade
                    if stripe_status in ['incomplete_expired', 'unpaid', 'canceled']:
                        self.stdout.write(
                            f"  Would downgrade to FREE due to status: {stripe_status}"
                        )
                else:
                    # Update subscription from Stripe
                    old_tier = subscription.tier
                    old_status = subscription.status
                    
                    # Update subscription using the helper function
                    _update_subscription_from_stripe(subscription, stripe_subscription)
                    
                    # Ensure status is mapped correctly (handle canceled vs cancelled)
                    if subscription.status != django_status:
                        subscription.status = django_status
                    
                    subscription.save()
                    
                    # Check if tier changed
                    if subscription.tier != old_tier:
                        logger.info(
                            f"Subscription {subscription.id} tier changed from {old_tier} to {subscription.tier}"
                        )
                        if subscription.tier == Subscription.TIER_FREE:
                            downgraded_count += 1
                    
                    # Check if status changed
                    if subscription.status != old_status:
                        logger.info(
                            f"Subscription {subscription.id} status changed from {old_status} to {subscription.status}"
                        )
                    
                    synced_count += 1
                    
            except Exception as e:
                logger.error(
                    f"Unexpected error processing subscription {subscription.id}: {str(e)}",
                    exc_info=True
                )
                error_count += 1
        
        # Summary
        if dry_run:
            self.stdout.write(
                self.style.WARNING(
                    f"DRY RUN: Would sync {synced_count} subscription(s), "
                    f"downgrade {downgraded_count} subscription(s), "
                    f"encounter {error_count} error(s)"
                )
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(
                    f"Successfully synced {synced_count} subscription(s), "
                    f"downgraded {downgraded_count} subscription(s), "
                    f"encountered {error_count} error(s)"
                )
            )
