# Testing Stripe Webhooks - Payment Failure & Subscription Expiration

## Setup

1. **Start your Django server** (if not already running):
   ```bash
   python manage.py runserver
   ```

2. **Start Stripe CLI webhook listener** (in a separate terminal):
   ```bash
   stripe listen --forward-to localhost:8000/subscription/webhook/
   ```
   
   This will output a webhook signing secret like: `whsec_...`
   Copy this and add it to your `.env` file:
   ```
   STRIPE_WEBHOOK_SECRET=whsec_...
   ```

## Test Scenarios

### Scenario 1: Payment Failure (invoice.payment_failed)

This simulates when a customer's payment method fails.

**Trigger the event:**
```bash
stripe trigger invoice.payment_failed
```

**What should happen:**
- Webhook receives `invoice.payment_failed` event
- Subscription status changes to `past_due`
- User still has access (status is past_due, not expired yet)
- Check Django logs for: "Subscription X payment failed, status set to past_due"

**Verify:**
- Check your database: `Subscription.objects.filter(status='past_due')`
- Check Django server logs for webhook processing messages

### Scenario 2: Subscription Expires (incomplete_expired)

This simulates when payment fails permanently and subscription expires.

**Trigger the event:**
```bash
stripe trigger customer.subscription.updated
```

**Or manually create a test subscription and let it expire:**
```bash
# Create a test subscription
stripe subscriptions create \
  --customer cus_test123 \
  --items[0][price]=price_1SUdLt8TJMYKOD9HkQsG0t55 \
  --payment_behavior=default_incomplete

# Then update it to expired status
stripe subscriptions update sub_test123 --status=incomplete_expired
```

**What should happen:**
- Webhook receives `customer.subscription.updated` with status `incomplete_expired`
- Subscription tier automatically reverts to `FREE`
- Subscription status becomes `incomplete_expired`
- User loses paid tier access immediately
- Check Django logs for: "Subscription X expired/unpaid, reverting to FREE tier"

**Verify:**
- Check database: Subscription tier should be `FREE`, status should be `incomplete_expired`
- User should see FREE tier limits in the app

### Scenario 3: Unpaid Status (unpaid)

This simulates when subscription becomes unpaid after retry period.

**Trigger:**
```bash
# Create test subscription and update to unpaid
stripe subscriptions update sub_test123 --status=unpaid
```

**What should happen:**
- Webhook receives `customer.subscription.updated` with status `unpaid`
- Subscription tier automatically reverts to `FREE`
- User loses paid tier access immediately

### Scenario 4: Payment Succeeds After Failure (invoice.payment_succeeded)

This simulates when payment succeeds after a previous failure.

**Trigger:**
```bash
stripe trigger invoice.payment_succeeded
```

**What should happen:**
- Webhook receives `invoice.payment_succeeded` event
- If subscription was `past_due`, it changes back to `active`
- User regains full access

## Monitoring Webhooks

### View Django Logs
Watch your Django server console for webhook events:
- `Received Stripe webhook event: invoice.payment_failed`
- `Processing invoice.payment_failed for subscription...`
- `Subscription X expired/unpaid, reverting to FREE tier`

### View Stripe CLI Output
The Stripe CLI will show:
- Events being forwarded
- HTTP response codes (should be 200)
- Any errors

### Check Database
```python
# In Django shell
from a_subscription.models import Subscription

# Check all subscriptions
Subscription.objects.all()

# Check expired/unpaid
Subscription.objects.filter(status__in=['incomplete_expired', 'unpaid'])

# Check past_due
Subscription.objects.filter(status='past_due')
```

## Expected Behavior Summary

| Event | Status Change | Tier Change | Access |
|-------|--------------|-------------|--------|
| `invoice.payment_failed` | → `past_due` | No change | Still has access |
| `customer.subscription.updated` (status: `incomplete_expired`) | → `incomplete_expired` | → `FREE` | Loses paid access |
| `customer.subscription.updated` (status: `unpaid`) | → `unpaid` | → `FREE` | Loses paid access |
| `invoice.payment_succeeded` (after failure) | → `active` | No change | Regains access |

## Testing with Real Subscription

To test with an actual subscription in your database:

1. **Get a subscription ID from your database:**
   ```python
   from a_subscription.models import Subscription
   sub = Subscription.objects.filter(tier__in=['STARTER', 'PRO']).first()
   print(sub.stripe_subscription_id)
   ```

2. **Update it in Stripe to trigger webhook:**
   ```bash
   stripe subscriptions update <subscription_id> --status=incomplete_expired
   ```

3. **Check your database to see if tier changed to FREE**

## Troubleshooting

- **Webhook not received?** Check that Stripe CLI is running and forwarding to correct URL
- **Signature verification failed?** Make sure `STRIPE_WEBHOOK_SECRET` is set in `.env`
- **No changes in database?** Check Django logs for errors, verify subscription exists in database
- **Wrong tier?** Check that price IDs are correctly mapped in `get_tier_from_price_id()`

