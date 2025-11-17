# Family Management SaaS

A private SaaS application for family task management, rewards, and organization. This Django-based platform helps families coordinate tasks, manage rewards, and stay organized with features like shopping lists.

## Table of Contents

- [Features](#features)
- [Technology Stack](#technology-stack)
- [Project Structure](#project-structure)
- [Setup & Installation](#setup--installation)
- [Environment Variables](#environment-variables)
- [Database](#database)
- [Development](#development)
- [Application Overview](#application-overview)
- [Subscription Tiers](#subscription-tiers)

## Features

- **Family Management**: Create families with owners and members (parents/children)
- **Task Management**: Create, assign, and track tasks with priorities, due dates, and points
- **Rewards System**: Claim rewards using earned points
- **Shopping Lists**: Shared shopping lists for families (premium feature)
- **Subscription Management**: Stripe-integrated subscription system with tiered plans
- **User Authentication**: Email/username-based authentication via django-allauth
- **Dashboard**: Centralized dashboard for family management

## Technology Stack

- **Backend**: Django 5.2.8
- **Authentication**: django-allauth
- **Payments**: Stripe
- **Database**: SQLite (development)
- **Python**: 3.14+

## Project Structure

```
Family v1/
├── _core/                    # Core Django settings and configuration
│   ├── settings.py          # Main settings file
│   ├── urls.py              # Root URL configuration
│   └── ...
├── a_dashboard/             # Dashboard application
├── a_family/                # Family management
│   ├── models.py           # Family and UserProfile models
│   └── forms.py            # Custom signup form
├── a_landing/               # Landing page and marketing
├── a_rewards/               # Rewards system
├── a_shopping/              # Shopping list feature
├── a_subscription/          # Subscription and billing
│   ├── models.py           # Subscription models
│   └── utils.py            # Subscription utilities and limits
├── a_tasks/                 # Task management
├── static/                  # Static files (CSS, JS)
├── templates/               # HTML templates
└── manage.py               # Django management script
```

## Setup & Installation

### Prerequisites

- Python 3.14+
- pip
- Virtual environment (recommended)

### Installation Steps

1. **Clone the repository** (if not already cloned)

2. **Create and activate a virtual environment**:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies**:
   ```bash
   pip install django==5.2.8
   pip install django-allauth
   pip install stripe
   pip install python-dotenv
   ```

   Or create a `requirements.txt` with:
   ```
   Django==5.2.8
   django-allauth
   stripe
   python-dotenv
   ```
   Then run: `pip install -r requirements.txt`

4. **Set up environment variables**:
   Create a `.env` file in the project root (see [Environment Variables](#environment-variables))

5. **Run migrations**:
   ```bash
   python manage.py migrate
   ```

6. **Create a superuser** (optional, for admin access):
   ```bash
   python manage.py createsuperuser
   ```

7. **Run the development server**:
   ```bash
   python manage.py runserver
   ```

8. **Access the application**:
   - Main site: http://127.0.0.1:8000/
   - Admin panel: http://127.0.0.1:8000/admin/
   - Dashboard: http://127.0.0.1:8000/dashboard/

## Environment Variables

Create a `.env` file in the project root with the following variables:

```env
# Django Secret Key (generate a new one for production)
SECRET_KEY=your-secret-key-here

# Stripe Configuration
STRIPE_PUBLIC_KEY=pk_test_...
STRIPE_SECRET_KEY=sk_test_...

# Database (optional, defaults to SQLite)
# DATABASE_URL=postgresql://user:password@localhost/dbname
```

**Important**: Never commit the `.env` file to version control. It should be in `.gitignore`.

## Database

### Current Setup
- **Development**: SQLite (`db.sqlite3`)
- **Production**: Configure a PostgreSQL database via `DATABASE_URL` in `.env`

### Migrations
- Run migrations: `python manage.py migrate`
- Create new migrations: `python manage.py makemigrations`

### Key Models
- **Family**: Family groups with owner and members
- **UserProfile**: Extended user profile with role (parent/child) and points
- **Subscription**: User subscriptions with tier and Stripe integration
- **Task**: Tasks assigned to family members
- **Reward**: Rewards that can be claimed with points
- **ShoppingListItem**: Items in family shopping lists

## Development

### Running the Development Server
```bash
python manage.py runserver
```

### Creating Migrations
After modifying models:
```bash
python manage.py makemigrations
python manage.py migrate
```

### Django Admin
Access the admin panel at `/admin/` after creating a superuser:
```bash
python manage.py createsuperuser
```

### Static Files
Collect static files for production:
```bash
python manage.py collectstatic
```

### Testing
```bash
python manage.py test
```

## Application Overview

### Apps

#### `a_family`
- **Family Model**: Represents a family group with an owner and members
- **UserProfile Model**: Extends User with role (parent/child) and points
- **Custom Signup**: `FamilySignupForm` for family creation during signup

#### `a_tasks`
- Task creation, assignment, and completion
- Priority levels (Low, Medium, High)
- Points system for task completion
- Task approval workflow

#### `a_rewards`
- Reward creation with point costs
- Reward claiming system
- Points-based redemption

#### `a_shopping`
- Shared shopping lists for families
- Premium feature (requires STARTER or PRO subscription)

#### `a_subscription`
- Stripe integration for subscription management
- Three tiers: FREE, STARTER, PRO
- Usage tracking (tasks/rewards per month)
- Subscription status management

#### `a_dashboard`
- Main dashboard for authenticated users
- Family overview and management

#### `a_landing`
- Public landing pages
- Features, pricing, about pages

### URL Patterns

- `/` - Landing page
- `/accounts/` - Authentication (allauth)
- `/dashboard/` - User dashboard
- `/subscription/` - Subscription management
- `/tasks/` - Task management
- `/rewards/` - Rewards system
- `/shopping/` - Shopping lists
- `/admin/` - Django admin

## Subscription Tiers

### FREE Tier
- 1 parent
- 1 child
- 5 tasks per month
- 3 rewards per month
- ❌ Shopping list access

### STARTER Tier
- 2 parents
- 2 children
- 20 tasks per month
- 15 rewards per month
- ✅ Shopping list access

### PRO Tier
- 4 parents
- 10 children
- 100 tasks per month
- 50 rewards per month
- ✅ Shopping list access

### Stripe Price IDs

Configured in `_core/settings.py`:
- `STARTER_MONTHLY_PRICE_ID`
- `STARTER_YEARLY_PRICE_ID`
- `PRO_MONTHLY_PRICE_ID`
- `PRO_YEARLY_PRICE_ID`

Update these with your actual Stripe Price IDs.

## Authentication

- Uses django-allauth for authentication
- Login methods: username or email
- Email verification: Disabled (can be enabled in settings)
- Custom signup form: `a_family.forms.FamilySignupForm`
- Login redirect: `/dashboard/`

## Notes for Developers

### Subscription Limits
Subscription limits are enforced in `a_subscription/utils.py`. When adding features, check:
- `check_subscription_limit()` - Verify if resource creation is allowed
- `increment_usage()` - Update monthly usage counters
- `can_add_member()` - Verify member addition limits

### Family Model
- Family ID is a random 6-digit integer (100000-999999)
- Each family has one owner (User)
- Members are added via ManyToMany relationship
- Subscription is tied to the family owner

### Points System
- Users earn points by completing tasks
- Points are stored in `UserProfile.points`
- Rewards can be claimed using points

### Development vs Production
- Set `DEBUG = False` in production
- Use a proper database (PostgreSQL) in production
- Configure proper `ALLOWED_HOSTS`
- Set up proper email backend for production
- Use environment variables for all secrets

## Contributing

This is a private SaaS project. Follow these guidelines:

1. Create feature branches from `master`
2. Write meaningful commit messages
3. Test changes thoroughly before committing
4. Run migrations before pushing database changes
5. Update this README when adding new features or changing architecture

## License

Private - All rights reserved

