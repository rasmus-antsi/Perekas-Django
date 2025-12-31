#!/usr/bin/env python
"""
Send a test review request email (client-facing)
"""
import os
import django
import sys
import logging
from pathlib import Path

# Change to project root directory (parent of scripts/)
script_dir = Path(__file__).parent
project_root = script_dir.parent
sys.path.insert(0, str(project_root))
os.chdir(project_root)

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', '_core.settings')
django.setup()

from django.test import RequestFactory
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from django.conf import settings
from django.urls import reverse
from a_family.models import User
from a_family.emails import _get_logo_url
import time

# Setup logging
logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# Create a mock request
factory = RequestFactory()
request = factory.get('/', SERVER_NAME='perekas.ee')
request.META['HTTP_X_FORWARDED_PROTO'] = 'https'
request.META['wsgi.url_scheme'] = 'https'

# Get user
user = User.objects.filter(email='rasmus435@icloud.com').first()
if not user:
    logger.error("User rasmus435@icloud.com not found!")
    sys.exit(1)

logger.info(f"User: {user.get_display_name()} ({user.email})")
logger.info("Sending review request email synchronously...")

try:
    # Send synchronously for testing
    dashboard_url = request.build_absolute_uri(reverse('a_dashboard:dashboard'))
    review_form_url = request.build_absolute_uri(reverse('a_landing:review_form'))
    logo_url = _get_logo_url(request)
    
    context = {
        'user': user,
        'user_name': user.get_display_name(),
        'dashboard_url': dashboard_url,
        'review_form_url': review_form_url,
        'logo_url': logo_url,
    }
    
    html_body = render_to_string('email/review_request.html', context)
    text_body = strip_tags(html_body)
    
    email = EmailMultiAlternatives(
        subject="Kas Perekas sobib sinu perele?",
        body=text_body,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[user.email],
    )
    email.attach_alternative(html_body, "text/html")
    email.send(fail_silently=False)
    
    logger.info("✓ Review request email sent successfully!")
    logger.info("Check your inbox at rasmus435@icloud.com")
except Exception as e:
    logger.error(f"✗ Failed to send review request email: {e}", exc_info=True)
    sys.exit(1)

