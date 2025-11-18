# Deployment Guide - Perekas Django

This guide covers deploying the Perekas Django application to production on Railway (or similar platforms).

## Prerequisites

- Railway account (or similar platform)
- Stripe account with production API keys
- Domain name (optional, Railway provides free subdomain)
- Email SMTP credentials
- **Note**: This project uses Python 3.12 for production stability and package compatibility

## Pre-Deployment Checklist

### 1. Environment Variables

Set the following environment variables in your Railway project (or platform):

#### Required Variables

```bash
# Django
SECRET_KEY=<generate-new-secret-key>
DEBUG=False
# IMPORTANT: Replace 'your-app-name' with your actual Railway app name
# Django doesn't support wildcards, so you must specify exact domains
ALLOWED_HOSTS=www.perekas.ee,perekas.ee,your-app-name.railway.app

# Database (automatically set by Railway when PostgreSQL is added)
# DATABASE_URL is provided automatically by Railway

# Stripe Production Keys
STRIPE_PUBLIC_KEY=pk_live_...
STRIPE_SECRET_KEY=sk_live_...
STRIPE_WEBHOOK_SECRET=whsec_...

# Stripe Price IDs (Production)
STARTER_MONTHLY_PRICE_ID=price_...
STARTER_YEARLY_PRICE_ID=price_...
PRO_MONTHLY_PRICE_ID=price_...
PRO_YEARLY_PRICE_ID=price_...

# Email SMTP
EMAIL_HOST=smtp.veebimajutus.ee
EMAIL_PORT=465
EMAIL_USE_TLS=False
EMAIL_USE_SSL=True
EMAIL_HOST_USER=your-email@perekas.ee
EMAIL_HOST_PASSWORD=your-email-password
DEFAULT_FROM_EMAIL=noreply@perekas.ee

# Security
SECURE_SSL_REDIRECT=True
SECURE_HSTS_SECONDS=31536000
CSRF_TRUSTED_ORIGINS=https://www.perekas.ee,https://perekas.ee
```

### 2. Generate Secret Key

Generate a new Django secret key for production:

```bash
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

### 3. Stripe Configuration

#### Create Production Price IDs

1. Go to Stripe Dashboard → Products
2. Create/update your products for Starter and Pro tiers
3. Create monthly and yearly prices for each tier
4. Copy the Price IDs and add them to environment variables

#### Set Up Webhook Endpoint

1. Go to Stripe Dashboard → Developers → Webhooks
2. Click "Add endpoint"
3. Enter your webhook URL: `https://www.perekas.ee/subscription/webhook/`
   - **Note**: The endpoint accepts both `/subscription/webhook/` and `/subscription/webhook` (with or without trailing slash)
4. Select events to listen for:
   - `customer.subscription.created`
   - `customer.subscription.updated`
   - `customer.subscription.deleted`
   - `invoice.payment_succeeded`
   - `invoice.payment_failed`
5. Copy the webhook signing secret (starts with `whsec_`) and add to `STRIPE_WEBHOOK_SECRET` environment variable
6. **Important**: Use the production webhook secret for production, and test secret for local development

## Railway Deployment Steps

### 1. Create Railway Project

1. Go to [Railway.app](https://railway.app)
2. Click "New Project"
3. Select "Deploy from GitHub repo" (or upload code)

### 2. Add PostgreSQL Database

1. In your Railway project, click "New"
2. Select "Database" → "Add PostgreSQL"
3. Railway automatically sets `DATABASE_URL` environment variable

### 3. Configure Environment Variables

1. Go to your Railway project → Variables
2. Add all environment variables from the checklist above
3. Make sure `DEBUG=False` for production

### 4. Deploy

Railway will automatically:
- Detect Python project
- Install dependencies from `requirements.txt`
- Run migrations via `Procfile` release command
- Collect static files via `Procfile` release command
- Start the application with gunicorn

### 5. Custom Domain (Optional)

1. Go to Railway project → Settings → Domains
2. Add your custom domain (e.g., `www.perekas.ee`)
3. Railway automatically provisions SSL certificate
4. **Important**: Update `ALLOWED_HOSTS` environment variable with:
   - Your Railway subdomain: `your-app-name.railway.app`
   - Your custom domain: `www.perekas.ee,perekas.ee`
   - Update `CSRF_TRUSTED_ORIGINS` with: `https://www.perekas.ee,https://perekas.ee`
   - **Note**: Django doesn't support wildcards in ALLOWED_HOSTS, so you must specify exact domains

## Post-Deployment Verification

### 1. Test Application

- [ ] Visit homepage: `https://www.perekas.ee`
- [ ] Test user registration
- [ ] Test email verification
- [ ] Test login
- [ ] Test subscription upgrade flow
- [ ] Test Stripe webhook (use Stripe CLI or test payment)

### 2. Test Stripe Webhook

Using Stripe CLI:

```bash
stripe listen --forward-to https://www.perekas.ee/subscription/webhook/
```

Or test via Stripe Dashboard:
1. Go to Webhooks → Your endpoint → Send test webhook
2. Test events: `customer.subscription.created`, `customer.subscription.updated`

### 3. Verify Security Settings

- [ ] HTTPS redirect works (HTTP → HTTPS)
- [ ] Security headers are set (check with [SecurityHeaders.com](https://securityheaders.com))
- [ ] CSRF protection works
- [ ] Session cookies are secure

### 4. Check Logs

Monitor Railway logs for any errors:
- Database connection issues
- Stripe webhook errors
- Email sending errors
- Static file serving issues

## Database Migrations

Migrations run automatically via the `Procfile` release command:

```
release: python manage.py migrate --noinput && python manage.py collectstatic --noinput
```

To manually run migrations:

```bash
railway run python manage.py migrate
```

## Static Files

Static files are automatically collected during deployment via the `Procfile` release command and served by WhiteNoise middleware.

## Monitoring & Logging

### Railway Logs

View logs in Railway dashboard:
- Real-time logs
- Error tracking
- Performance metrics

### Application Logs

Logs are written to:
- Console (visible in Railway logs)
- File: `/logs/django.log` (if configured)

## Backup Strategy

### Database Backups

Railway PostgreSQL includes automatic backups. To manually backup:

```bash
# Export database
railway run python manage.py dumpdata > backup.json

# Or use pg_dump
railway run pg_dump $DATABASE_URL > backup.sql
```

### Recommended Backup Schedule

- Daily automated backups (Railway default)
- Weekly manual exports for critical data
- Before major deployments

## Rollback Plan

### If Deployment Fails

1. **Immediate Rollback**: Railway allows you to rollback to previous deployment
2. **Database Rollback**: If migrations fail, you may need to manually rollback:
   ```bash
   railway run python manage.py migrate <app_name> <previous_migration>
   ```
3. **Environment Variables**: Revert any changed environment variables

### Emergency Procedures

1. Set `DEBUG=True` temporarily to see errors (remove immediately after)
2. Check Railway logs for specific errors
3. Verify all environment variables are set correctly
4. Test database connection
5. Verify Stripe webhook endpoint is accessible

## Troubleshooting

### Common Issues

#### 1. Static Files Not Loading

- Verify `collectstatic` ran successfully (check release logs)
- Check WhiteNoise middleware is enabled
- Verify `STATIC_ROOT` is set correctly

#### 2. Database Connection Errors

- Verify `DATABASE_URL` is set correctly
- Check PostgreSQL service is running in Railway
- Verify database credentials

#### 3. Stripe Webhook Failures

- Verify `STRIPE_WEBHOOK_SECRET` is set correctly
- Check webhook URL is accessible: `https://www.perekas.ee/subscription/webhook/`
- Verify webhook events are selected in Stripe Dashboard
- Check application logs for webhook errors

#### 4. Email Not Sending

- Verify SMTP credentials are correct
- Check `EMAIL_HOST`, `EMAIL_PORT`, `EMAIL_USE_SSL` settings
- Test email sending manually:
  ```bash
  railway run python manage.py sendtestemail
  ```

#### 5. CSRF Errors

- Verify `CSRF_TRUSTED_ORIGINS` includes your domain
- Check `SECURE_SSL_REDIRECT` is set correctly
- Verify HTTPS is working

#### 7. psycopg2 Import Errors

If you see errors like `Error loading psycopg2 or psycopg module` or `undefined symbol: _PyInterpreterState_Get`:

- **Cause**: `psycopg2-binary` doesn't have pre-built wheels for Python 3.14+
- **Solution**: This project uses Python 3.12 (specified in `runtime.txt`) for better package compatibility
- If you need to use Python 3.14, consider switching to `psycopg` (psycopg3) instead of `psycopg2-binary`

## Performance Optimization

### Database

- Enable connection pooling (Railway PostgreSQL includes this)
- Add database indexes for frequently queried fields
- Use `select_related` and `prefetch_related` in views

### Static Files

- WhiteNoise compresses and caches static files automatically
- Consider CDN for static assets (optional)

### Caching

- Consider adding Redis for session storage and caching
- Use Django's cache framework for frequently accessed data

## Security Checklist

- [x] `DEBUG=False` in production
- [x] `SECRET_KEY` is unique and secure
- [x] `ALLOWED_HOSTS` is configured
- [x] HTTPS is enforced (`SECURE_SSL_REDIRECT=True`)
- [x] HSTS is enabled
- [x] Secure cookies are enabled
- [x] CSRF protection is enabled
- [x] Stripe webhook signature verification is enabled
- [x] Database credentials are secure (not in code)
- [x] Email credentials are secure (not in code)

## Support & Resources

- Railway Documentation: https://docs.railway.app
- Django Deployment Checklist: https://docs.djangoproject.com/en/5.2/howto/deployment/checklist/
- Stripe Webhooks Guide: https://stripe.com/docs/webhooks

