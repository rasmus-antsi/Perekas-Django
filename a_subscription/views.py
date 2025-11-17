import json
from datetime import datetime
import stripe
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect, get_object_or_404
from django.conf import settings
from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse, HttpResponse
from django.utils import timezone

from a_family.models import Family
from .models import Subscription
from .utils import (
    get_user_subscription,
    get_family_subscription,
    get_current_month_usage,
    get_tier_limits,
)


def _get_family_for_user(user):
    """Helper to get family for a user"""
    family = None
    if hasattr(user, "families"):
        family = user.families.first()
    if family is None:
        family = Family.objects.filter(owner=user).first()
    return family


@login_required
def subscription_status(request):
    """Show current subscription status and usage"""
    user = request.user
    family = _get_family_for_user(user)

    # Only family owner can view subscription
    if not family or family.owner != user:
        messages.error(request, "Tellimuse vaatamiseks peab olema pere looja.")
        return redirect('a_dashboard:dashboard')

    tier = get_family_subscription(family)
    limits = get_tier_limits(tier)
    usage = get_current_month_usage(family)

    # Get active subscription if exists
    subscription = Subscription.objects.filter(
        owner=user,
        tier__in=[Subscription.TIER_STARTER, Subscription.TIER_PRO]
    ).first()

    tasks_created = usage.tasks_created if usage else 0
    rewards_created = usage.rewards_created if usage else 0

    context = {
        'family': family,
        'tier': tier,
        'display_tier': dict(Subscription.TIER_CHOICES).get(tier, tier),
        'subscription': subscription,
        'limits': limits,
        'usage': usage,
        'tasks_remaining': max(0, limits['max_tasks_per_month'] - tasks_created),
        'rewards_remaining': max(0, limits['max_rewards_per_month'] - rewards_created),
    }
    return render(request, 'a_subscription/status.html', context)


@login_required
def upgrade(request):
    """Handle subscription upgrade via Stripe checkout"""
    user = request.user
    family = _get_family_for_user(user)

    # Only family owner can upgrade
    if not family or family.owner != user:
        messages.error(request, "Tellimuse uuendamiseks peab olema pere looja.")
        return redirect('a_dashboard:dashboard')

    if request.method == 'POST':
        tier = request.POST.get('tier')
        billing_period = request.POST.get('billing_period', 'monthly')  # monthly or yearly

        if tier not in [Subscription.TIER_STARTER, Subscription.TIER_PRO]:
            messages.error(request, "Vigane paketivalik.")
            return redirect('a_subscription:status')

        # Get appropriate price ID
        if tier == Subscription.TIER_STARTER:
            price_id = settings.STARTER_MONTHLY_PRICE_ID if billing_period == 'monthly' else settings.STARTER_YEARLY_PRICE_ID
        else:  # PRO
            price_id = settings.PRO_MONTHLY_PRICE_ID if billing_period == 'monthly' else settings.PRO_YEARLY_PRICE_ID

        if not settings.STRIPE_SECRET_KEY:
            messages.error(request, "Stripe pole seadistatud. Palun võta ühendust toega.")
            return redirect('a_subscription:status')

        stripe.api_key = settings.STRIPE_SECRET_KEY

        try:
            # Get or create Stripe customer
            subscription = Subscription.objects.filter(owner=user, tier=tier).first()
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
                cancel_url=request.build_absolute_uri('/subscription/status/'),
                metadata={
                    'user_id': user.id,
                    'family_id': family.id,
                    'tier': tier,
                }
            )

            return redirect(checkout_session.url)

        except stripe.error.StripeError as e:
            messages.error(request, f"Stripe'i viga: {str(e)}")
            return redirect('a_subscription:status')

    # GET request - show upgrade page
    current_tier = get_family_subscription(family)
    context = {
        'family': family,
        'current_tier': current_tier,
    }
    return render(request, 'a_subscription/upgrade.html', context)


@login_required
def upgrade_success(request):
    """Handle successful subscription upgrade"""
    session_id = request.GET.get('session_id')
    if not session_id:
        messages.error(request, "Vigane seanss.")
        return redirect('a_subscription:status')

    if not settings.STRIPE_SECRET_KEY:
        messages.error(request, "Stripe pole seadistatud.")
        return redirect('a_subscription:status')

    stripe.api_key = settings.STRIPE_SECRET_KEY

    try:
        session = stripe.checkout.Session.retrieve(session_id)
        user_id = session.metadata.get('user_id')
        family_id = session.metadata.get('family_id')
        tier = session.metadata.get('tier')

        if str(request.user.id) != str(user_id):
            messages.error(request, "See seanss ei kuulu sinu kontole.")
            return redirect('a_subscription:status')

        # Get or create subscription
        subscription, created = Subscription.objects.get_or_create(
            owner=request.user,
            defaults={
                'tier': tier,
                'stripe_customer_id': session.customer,
                'status': Subscription.STATUS_ACTIVE,
            }
        )

        if not created:
            subscription.tier = tier
            subscription.stripe_customer_id = session.customer
            subscription.status = Subscription.STATUS_ACTIVE

        # Get subscription details from Stripe
        if session.subscription:
            stripe_subscription = stripe.Subscription.retrieve(session.subscription)
            subscription.stripe_subscription_id = stripe_subscription.id
            subscription.status = stripe_subscription.status
            subscription.current_period_start = timezone.make_aware(
                datetime.fromtimestamp(stripe_subscription.current_period_start)
            )
            subscription.current_period_end = timezone.make_aware(
                datetime.fromtimestamp(stripe_subscription.current_period_end)
            )

        subscription.save()

        messages.success(request, f"Pakett uuendati tasemele {subscription.get_tier_display()}!")
        return redirect('a_subscription:status')

    except stripe.error.StripeError as e:
        messages.error(request, f"Tekkis viga tellimuse töötlemisel: {str(e)}")
        return redirect('a_subscription:status')


@login_required
def cancel(request):
    """Cancel subscription"""
    user = request.user
    family = _get_family_for_user(user)

    # Only family owner can cancel
    if not family or family.owner != user:
        messages.error(request, "Tellimuse tühistamiseks peab olema pere looja.")
        return redirect('a_dashboard:dashboard')

    subscription = Subscription.objects.filter(
        owner=user,
        tier__in=[Subscription.TIER_STARTER, Subscription.TIER_PRO]
    ).first()

    if not subscription:
        messages.info(request, "Sul pole tühistamiseks aktiivset tellimust.")
        return redirect('a_subscription:status')

    if request.method == 'POST':
        if subscription.stripe_subscription_id and settings.STRIPE_SECRET_KEY:
            stripe.api_key = settings.STRIPE_SECRET_KEY
            try:
                stripe_subscription = stripe.Subscription.retrieve(subscription.stripe_subscription_id)
                stripe.Subscription.modify(
                    subscription.stripe_subscription_id,
                    cancel_at_period_end=True
                )
                subscription.status = Subscription.STATUS_ACTIVE  # Still active until period ends
                subscription.save()
                messages.success(request, "Sinu tellimus tühistub arveldusperioodi lõpus.")
            except stripe.error.StripeError as e:
                messages.error(request, f"Viga tellimuse tühistamisel: {str(e)}")
        else:
            # Manual cancellation (no Stripe)
            subscription.status = Subscription.STATUS_CANCELLED
            subscription.save()
            messages.success(request, "Tellimus tühistati edukalt.")

        return redirect('a_subscription:status')

    context = {
        'family': family,
        'subscription': subscription,
    }
    return render(request, 'a_subscription/cancel.html', context)


@csrf_exempt
def webhook(request):
    """Handle Stripe webhooks"""
    if not settings.STRIPE_SECRET_KEY:
        return HttpResponse(status=400)

    stripe.api_key = settings.STRIPE_SECRET_KEY
    payload = request.body
    sig_header = request.META.get('HTTP_STRIPE_SIGNATURE')

    # In production, you should verify the webhook signature
    # For now, we'll process the events
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

    # Handle the event
    if event['type'] == 'customer.subscription.updated' or event['type'] == 'customer.subscription.deleted':
        subscription_obj = event['data']['object']
        try:
            subscription = Subscription.objects.get(
                stripe_subscription_id=subscription_obj['id']
            )
            subscription.status = subscription_obj['status']
            if subscription_obj.get('current_period_start'):
                subscription.current_period_start = timezone.make_aware(
                    datetime.fromtimestamp(subscription_obj['current_period_start'])
                )
            if subscription_obj.get('current_period_end'):
                subscription.current_period_end = timezone.make_aware(
                    datetime.fromtimestamp(subscription_obj['current_period_end'])
                )
            subscription.save()
        except Subscription.DoesNotExist:
            pass

    return HttpResponse(status=200)
