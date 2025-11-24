#!/usr/bin/env python
"""
Send template emails one by one for verification
"""
import os
import django
import sys

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', '_core.settings')
django.setup()

from django.test import RequestFactory
from django.contrib.sites.models import Site
from a_family.models import User, Family
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils.html import strip_tags
from django.conf import settings
from allauth.account.models import EmailAddress, EmailConfirmation
from allauth.account.utils import user_pk_to_url_str

# Create a mock request
factory = RequestFactory()
request = factory.get('/', SERVER_NAME='perekas.ee')
request.META['HTTP_X_FORWARDED_PROTO'] = 'https'
request.META['wsgi.url_scheme'] = 'https'

# Get user
user = User.objects.filter(email='rasmus435@icloud.com').first()
if not user:
    print("User not found!")
    exit(1)

family = Family.objects.filter(owner=user).first() or user.families.first()
if not family:
    print("Family not found!")
    exit(1)

child = family.members.filter(role='child', email__isnull=True).first() or family.members.filter(role='child').first()
if not child:
    print("Child not found!")
    exit(1)

print(f"User: {user.get_display_name()} ({user.email})")
print(f"Family: {family.name} (Code: {family.join_code})")
print(f"Child: {child.get_display_name()} (Role: {child.role}, Email: {child.email or 'None'})")
print("\n" + "="*60)

# Helper to send email synchronously
def send_email_sync(subject, template_name, context, recipients):
    """Send email synchronously"""
    if not recipients:
        return False
    
    try:
        html_body = render_to_string(template_name, context)
        text_body = strip_tags(html_body)
        
        if template_name.endswith('.html'):
            text_template = template_name.replace('.html', '.txt')
            try:
                text_body = render_to_string(text_template, context)
            except:
                pass
        
        email = EmailMultiAlternatives(
            subject=subject,
            body=text_body,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=recipients,
        )
        email.attach_alternative(html_body, "text/html")
        email.send(fail_silently=False)
        return True
    except Exception as e:
        print(f"   ✗ Error: {e}")
        import traceback
        traceback.print_exc()
        return False

# Send emails one by one
emails_to_send = [
    {
        'name': 'Family Created Email',
        'subject': 'Sinu pere on loodud',
        'template': 'email/family_created.html',
        'context_func': lambda: {
            'user': user,
            'family': family,
            'onboarding_url': request.build_absolute_uri(reverse('a_family:onboarding')),
        }
    },
    {
        'name': 'Family Member Joined Email',
        'subject': 'Uus liige liitus sinu perega',
        'template': 'email/family_member_joined.html',
        'context_func': lambda: {
            'family': family,
            'member': child,
            'member_name': child.get_display_name(),
            'member_role': child.get_role_display() if hasattr(child, 'get_role_display') else '',
            'dashboard_url': request.build_absolute_uri(reverse('a_dashboard:dashboard')),
        }
    },
    {
        'name': 'Password Reset Email',
        'subject': 'Parooli taastamine',
        'template': 'account/email/password_reset_key_message.html',
        'context_func': lambda: {
            'user': user,
            'password_reset_url': f"{request.META.get('wsgi.url_scheme', 'https')}://{Site.objects.get_current().domain}/account/password/reset/key/{user_pk_to_url_str(user)}/",
        }
    },
    {
        'name': 'Email Confirmation Email',
        'subject': 'Kinnita oma e-post',
        'template': 'account/email/email_confirmation_message.html',
        'context_func': lambda: {
            'user': user,
            'activate_url': f"{request.META.get('wsgi.url_scheme', 'https')}://{Site.objects.get_current().domain}/account/confirm-email/{EmailConfirmation.create(EmailAddress.objects.get_or_create(user=user, email=user.email, defaults={'primary': True, 'verified': False})[0]).key}/",
        }
    },
    {
        'name': 'Email Confirmation Signup Email',
        'subject': 'Kinnita oma e-post',
        'template': 'account/email/email_confirmation_signup_message.html',
        'context_func': lambda: {
            'user': user,
            'activate_url': f"{request.META.get('wsgi.url_scheme', 'https')}://{Site.objects.get_current().domain}/account/confirm-email/{EmailConfirmation.create(EmailAddress.objects.get_or_create(user=user, email=user.email, defaults={'primary': True, 'verified': False})[0]).key}/",
        }
    },
]

if len(sys.argv) > 1:
    # Send specific email by number
    email_num = int(sys.argv[1])
    if 1 <= email_num <= len(emails_to_send):
        email_config = emails_to_send[email_num - 1]
        print(f"\nSending: {email_config['name']}")
        context = email_config['context_func']()
        print(f"Context keys: {list(context.keys())}")
        if send_email_sync(
            subject=email_config['subject'],
            template_name=email_config['template'],
            context=context,
            recipients=[user.email]
        ):
            print(f"✓ Sent to {user.email}")
        else:
            print(f"✗ Failed to send")
    else:
        print(f"Invalid email number. Choose 1-{len(emails_to_send)}")
else:
    # List all emails
    print("\nAvailable emails to send:")
    print("="*60)
    for i, email_config in enumerate(emails_to_send, 1):
        print(f"{i}. {email_config['name']}")
        print(f"   Template: {email_config['template']}")
        print(f"   Subject: {email_config['subject']}")
        print()
    print("="*60)
    print(f"\nTo send an email, run:")
    print(f"  python send_template_emails.py <number>")
    print(f"\nExample: python send_template_emails.py 1")

