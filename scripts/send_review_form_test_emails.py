#!/usr/bin/env python
"""
Send test review form submission emails for verification
"""
import os
import django
import sys
import logging
from pathlib import Path
from datetime import datetime

# Change to project root directory (parent of scripts/)
script_dir = Path(__file__).parent
project_root = script_dir.parent
sys.path.insert(0, str(project_root))
os.chdir(project_root)

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', '_core.settings')
django.setup()

from django.test import RequestFactory
from a_family.emails import _get_logo_url, send_review_request_email
from a_family.models import User
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from django.conf import settings

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
        logger.error(f"Error sending email: {e}", exc_info=True)
        return False

# Test email scenarios
test_emails = [
    {
        'name': 'Review Form - User who tried but gave up',
        'subject': '[Perekas] Uus tagasiside: test1@example.com',
        'context': {
            'submission': None,  # Not needed for template
            'user': None,
            'user_name': None,
            'email': 'test1@example.com',
            'name': 'Mari Tamm',
            'why_created_account': 'Tahtsin proovida, kuidas see töötab. Nägin reklaami ja tundus huvitav.',
            'added_family_members': False,
            'created_tasks': False,
            'created_rewards': False,
            'created_shopping_lists': False,
            'what_prevented_usage': 'Ei saanud aru, kuidas pereliikmeid lisada. Liiga keeruline oli.',
            'feedback': 'Võiks olla selgem juhend või tutorial esimesel sisselogimisel.',
            'submitted_at': datetime.now(),
            'ip_address': '192.168.1.100',
        }
    },
    {
        'name': 'Review Form - User who created account but never used it',
        'subject': '[Perekas] Uus tagasiside: test2@example.com',
        'context': {
            'submission': None,
            'user': None,
            'user_name': None,
            'email': 'test2@example.com',
            'name': 'Jaanus Kask',
            'why_created_account': 'Lugesin funktsioonidest ja tundus kasulik. Tahtsin pereelu paremaks korraldada.',
            'added_family_members': False,
            'created_tasks': False,
            'created_rewards': False,
            'created_shopping_lists': False,
            'what_prevented_usage': 'Unustasin ära. Ei leidnud aega sellega tegeleda.',
            'feedback': 'Võiks olla meeldetuletused või e-kirjad, mis meenutavad rakendust kasutada.',
            'submitted_at': datetime.now(),
            'ip_address': '192.168.1.101',
        }
    },
]

# Get logo URL
logo_url = _get_logo_url(request)

# Add logo_url to all contexts
for email_config in test_emails:
    email_config['context']['logo_url'] = logo_url

recipient_email = 'rasmus435@icloud.com'

logger.info("="*60)
logger.info(f"Sending {len(test_emails)} test review form emails to {recipient_email}")
logger.info("="*60)

for i, email_config in enumerate(test_emails, 1):
    logger.info(f"\n{i}. {email_config['name']}")
    logger.info(f"   Subject: {email_config['subject']}")
    
    if send_email_sync(
        subject=email_config['subject'],
        template_name='email/review_form_submission.html',
        context=email_config['context'],
        recipients=[recipient_email]
    ):
        logger.info(f"   ✓ Sent successfully")
    else:
        logger.error(f"   ✗ Failed to send")

# Also send the review request email (client-facing)
logger.info("\n" + "="*60)
logger.info("Sending review request email (client-facing)...")
logger.info("="*60)

user = User.objects.filter(email='rasmus435@icloud.com').first()
if user:
    try:
        send_review_request_email(request, user)
        logger.info(f"✓ Review request email sent successfully")
    except Exception as e:
        logger.error(f"✗ Failed to send review request email: {e}")
else:
    logger.warning("User rasmus435@icloud.com not found, skipping review request email")

logger.info("\n" + "="*60)
logger.info("Done! Check your inbox at rasmus435@icloud.com")
logger.info("You should receive 3 emails:")
logger.info("  1. Review form submission (admin) - test1@example.com")
logger.info("  2. Review form submission (admin) - test2@example.com")
logger.info("  3. Review request email (client-facing)")

