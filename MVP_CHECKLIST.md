# MVP Checklist - Family Management SaaS

## ✅ What's Already Implemented

### Core Features
- ✅ User authentication (django-allauth with email verification)
- ✅ Family management (create, join, remove members)
- ✅ Task management (create, assign, complete, approve, points system)
- ✅ Rewards system (create, claim with points)
- ✅ Shopping lists (basic CRUD operations)
- ✅ Subscription system with Stripe integration
- ✅ Dashboard with statistics
- ✅ Landing pages (index, features, about, plans)
- ✅ Role-based access control (parent/child)
- ✅ Subscription tier limits enforcement
- ✅ Monthly usage tracking

---

## 🔴 Critical Issues (Must Fix Before MVP)

### 1. Production Security & Configuration
- [x] **Move SECRET_KEY to environment variable** - ✅ Done: Uses os.getenv('SECRET_KEY')
- [x] **Set DEBUG = False for production** - ✅ Done: Uses os.getenv('DEBUG'), defaults to True for local
- [x] **Configure ALLOWED_HOSTS** - ✅ Done: Configured via environment variable, supports Railway domains
- [x] **Configure production email backend** - ✅ Done: SMTP configured with environment variables (port 465, SSL)
- [ ] **Set up proper SECURE_SSL_REDIRECT, SECURE_HSTS_SECONDS, etc.** for HTTPS
- [x] **Move Stripe keys to environment variables** - ✅ Done: All Stripe keys use os.getenv()

### 2. Stripe Webhook Security
- [x] **Implement proper webhook signature verification** - ✅ Done: Webhook verification implemented (uses secret if set)
- [x] **Add STRIPE_WEBHOOK_SECRET to environment variables** - ✅ Done: STRIPE_WEBHOOK_SECRET configured in settings
- [x] **Test webhook handling for all subscription events** - ✅ Done: All events tested (created, updated, deleted, payment failed, payment succeeded)
- [x] **Handle subscription downgrades** - ✅ Done: Subscription expires/cancelled properly reverts to FREE tier

### 3. Database & Migrations
- [x] **Set up PostgreSQL for production** - ✅ Done: PostgreSQL configured via DATABASE_URL on Railway
- [x] **Create production database configuration** - ✅ Done: Uses dj-database-url to parse DATABASE_URL
- [x] **Test all migrations on clean database** - ✅ Done: Migrations run automatically via Procfile release command
- [ ] **Create database backup strategy**

### 4. Admin Panel
- [x] **Register Task model in admin** - Currently not registered
- [x] **Register Reward model in admin** - Currently not registered
- [x] **Register ShoppingListItem model in admin** - Currently not registered
- [x] **Add useful list filters and search fields for all models**

---

## 🟡 Important Features (Should Have for MVP)

### 5. Settings Page Functionality
- [ ] **Implement settings save functionality** - Currently only displays, doesn't save
- [ ] **Add user profile update (name, email)**
- [ ] **Add role change functionality (if needed)**
- [ ] **Add notification preferences saving** - Currently hardcoded

### 6. Subscription Management
- [x] **Add subscription downgrade handling** - ✅ Done: When subscription expires, reverts to FREE tier via webhook
- [x] **Add usage reset automation** - ✅ Done: Usage resets based on subscription period start (paid subscriptions use Stripe period, FREE tier uses 30-day periods from family creation)
- [ ] **Add subscription renewal reminders** (optional but recommended)
- [x] **Handle payment failures gracefully** - ✅ Done: Payment failures set to past_due, expiration reverts to FREE
- [x] **Add subscription upgrade/downgrade between tiers** - ✅ Done: Prorated upgrades/downgrades implemented

### 7. Error Handling & Edge Cases
- [ ] **Add proper 404/500 error pages**
- [ ] **Handle edge cases in task approval** (what if task is deleted while pending?)
- [ ] **Handle edge cases in reward claiming** (what if user points change between page load and claim?)
- [ ] **Add validation for family member limits before joining**
- [ ] **Handle concurrent task completion/approval**
- [ ] **Add transaction handling for points updates** (prevent race conditions)

### 8. Email Functionality
- [x] **Set up production email backend** - ✅ Done: SMTP configured with veebimajutus.ee (port 465, SSL)
- [ ] **Test email verification flow end-to-end**
- [ ] **Test password reset flow end-to-end**
- [ ] **Add email notifications for:**
  - [ ] Task assignments
  - [ ] Task completions (for parents)
  - [ ] Task approvals (for children)
  - [ ] Reward claims
  - [ ] Family member joins
  - [ ] Subscription status changes

### 9. Static Files & Media
- [x] **Configure STATIC_ROOT and STATIC_URL properly** - ✅ Done: STATIC_ROOT and STATIC_URL configured
- [x] **Set up static file collection for production** - ✅ Done: collectstatic in Procfile, WhiteNoise middleware configured
- [ ] **Configure MEDIA_ROOT and MEDIA_URL if needed**
- [ ] **Test static file serving in production**

### 10. Logging & Monitoring
- [ ] **Set up logging configuration**
- [ ] **Add error logging for critical operations**
- [ ] **Set up monitoring/alerting (optional but recommended)**

---

## 🟢 Nice to Have (Post-MVP)

### 11. Testing
- [ ] **Write unit tests for models**
- [ ] **Write integration tests for views**
- [ ] **Write tests for subscription logic**
- [ ] **Write tests for points system**
- [ ] **Set up CI/CD pipeline**

### 12. Additional Features
- [ ] **Family owner transfer functionality**
- [ ] **Task recurrence/scheduling**
- [ ] **Task categories/tags**
- [ ] **Reward categories**
- [ ] **Shopping list categories**
- [ ] **Activity feed/history**
- [ ] **Export data functionality**
- [ ] **Mobile-responsive improvements**

### 13. Performance
- [ ] **Add database query optimization** (use select_related/prefetch_related where needed)
- [ ] **Add caching for frequently accessed data**
- [ ] **Optimize dashboard queries**

### 14. Documentation
- [ ] **API documentation (if needed)**
- [ ] **Deployment guide**
- [ ] **User guide/documentation**

---

## 📋 Pre-Launch Checklist

### Environment Setup
- [x] Create `.env.example` file with all required variables - ✅ Done: .env.example created with all variables
- [ ] Document all environment variables in README
- [ ] Set up production environment variables (in Railway)
- [x] Configure production database - ✅ Done: PostgreSQL configured on Railway
- [x] Set up production email service - ✅ Done: SMTP configured

### Security Audit
- [ ] Review all user inputs for XSS vulnerabilities
- [ ] Review all database queries for SQL injection (Django ORM should handle this)
- [ ] Review CSRF protection (Django has this by default)
- [ ] Review authentication and authorization checks
- [ ] Review subscription payment flow security
- [ ] Set up security headers (CSP, X-Frame-Options, etc.)

### Testing
- [ ] Test complete user signup flow
- [ ] Test family creation and joining
- [ ] Test task creation, completion, and approval
- [ ] Test reward creation and claiming
- [ ] Test shopping list functionality
- [ ] Test subscription upgrade flow
- [ ] Test subscription cancellation
- [ ] Test webhook handling
- [ ] Test email verification
- [ ] Test password reset
- [ ] Test edge cases and error scenarios

### Deployment
- [x] Set up production server/hosting - ✅ Done: Railway deployment configured
- [x] Configure domain and SSL certificate - ✅ Done: www.perekas.ee configured, Railway provides SSL
- [ ] Set up database backups
- [x] Configure static file serving - ✅ Done: WhiteNoise configured, collectstatic in Procfile
- [ ] Set up monitoring and logging
- [ ] Test deployment process
- [ ] Create rollback plan

---

## 🔍 Code Quality Issues Found

1. ~~**Settings.py**: Hardcoded secrets (SECRET_KEY, Stripe keys)~~ ✅ Fixed: All use environment variables
2. ~~**Settings.py**: DEBUG = True (should be False in production)~~ ✅ Fixed: Configurable via environment variable
3. ~~**Settings.py**: ALLOWED_HOSTS = [] (needs production hosts)~~ ✅ Fixed: Configured via environment variable
4. ~~**a_subscription/views.py**: Webhook signature verification incomplete~~ ✅ Fixed: Webhook verification implemented
5. ~~**Admin panels**: Missing registrations for Task, Reward, ShoppingListItem~~ ✅ Fixed
6. **a_dashboard/views.py**: Settings view doesn't save changes
7. ~~**No automated monthly usage reset** - relies on get_current_month_usage creating new records~~ ✅ Fixed: Usage now resets based on subscription period start dates
8. ~~**No subscription downgrade handling** when subscription expires~~ ✅ Fixed: Webhook handles expiration and reverts to FREE
9. ~~**Email backend**: Using console backend (needs production SMTP)~~ ✅ Fixed: SMTP configured

---

## 📝 Notes

- The core functionality is well-implemented and the code structure is good
- Most critical issues are configuration-related for production deployment
- The subscription system is functional but needs better error handling
- Email notifications would significantly improve user experience
- Admin panel needs completion for easier content management

---

## Priority Order for MVP

1. **Critical Security** (Items 1-2) - Must fix before any production deployment
2. **Database Setup** (Item 3) - Required for production
3. **Admin Panel** (Item 4) - Needed for content management
4. **Settings Functionality** (Item 5) - Core user feature
5. **Subscription Edge Cases** (Item 6) - Important for payment handling
6. **Error Handling** (Item 7) - Improves stability
7. **Email Setup** (Item 8) - Required for email verification to work
8. **Static Files** (Item 9) - Required for production
9. **Logging** (Item 10) - Important for debugging production issues

