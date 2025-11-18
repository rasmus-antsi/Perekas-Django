import json
from datetime import datetime
import stripe
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect
from django.conf import settings
from django.views.decorators.csrf import csrf_exempt
from django.http import HttpResponse
from django.utils import timezone

from .models import Subscription




@login_required
def upgrade_success(request):
    """Handle successful subscription upgrade"""
    session_id = request.GET.get('session_id')
    if not session_id:
        messages.error(request, "Vigane seanss.")
        return redirect('a_dashboard:settings')

    if not settings.STRIPE_SECRET_KEY:
        messages.error(request, "Stripe pole seadistatud.")
        return redirect('a_dashboard:settings')

    stripe.api_key = settings.STRIPE_SECRET_KEY

    try:
        session = stripe.checkout.Session.retrieve(session_id)
        user_id = session.metadata.get('user_id')
        family_id = session.metadata.get('family_id')
        tier = session.metadata.get('tier')

        if str(request.user.id) != str(user_id):
            messages.error(request, "See seanss ei kuulu sinu kontole.")
            return redirect('a_dashboard:settings')

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
        return redirect('a_dashboard:settings')

    except stripe.error.StripeError as e:
        messages.error(request, f"Tekkis viga tellimuse töötlemisel: {str(e)}")
        return redirect('a_dashboard:settings')




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
