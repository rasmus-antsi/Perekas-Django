import logging
import threading

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template import TemplateDoesNotExist
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils.html import strip_tags


logger = logging.getLogger(__name__)


def _send_branded_email(subject: str, template_name: str, context: dict, recipients: list[str]) -> None:
    """
    Render and send a rich email with HTML + plaintext fallback.
    Sending happens on a background thread to keep HTTP requests snappy.
    """
    if not recipients:
        return

    def _deliver():
        try:
            html_body = render_to_string(template_name, context)
            text_body = strip_tags(html_body)

            if template_name.endswith('.html'):
                text_template = template_name.replace('.html', '.txt')
                try:
                    text_body = render_to_string(text_template, context)
                except TemplateDoesNotExist:
                    pass

            email_message = EmailMultiAlternatives(
                subject=subject,
                body=text_body,
                from_email=settings.DEFAULT_FROM_EMAIL,
                to=recipients,
            )
            email_message.attach_alternative(html_body, "text/html")
            email_message.send()
        except Exception:
            logger.exception("Failed to send branded email '%s' to %s", subject, recipients)

    threading.Thread(target=_deliver, daemon=True).start()


def send_family_created_email(request, user, family):
    onboarding_url = request.build_absolute_uri(reverse('a_family:onboarding'))
    context = {
        'user': user,
        'family': family,
        'onboarding_url': onboarding_url,
    }
    _send_branded_email(
        subject="Sinu pere on loodud",
        template_name='email/family_created.html',
        context=context,
        recipients=[user.email] if user.email else [],
    )


def send_family_member_joined_email(request, family, member):
    dashboard_url = request.build_absolute_uri(reverse('a_dashboard:dashboard'))
    context = {
        'family': family,
        'member_name': member.get_full_name() or member.username,
        'member_role': member.get_role_display() if hasattr(member, 'get_role_display') else '',
        'dashboard_url': dashboard_url,
    }
    owner_email = family.owner.email if family.owner and family.owner.email else None
    if owner_email:
        _send_branded_email(
            subject="Uus liige liitus sinu perega",
            template_name='email/family_member_joined.html',
            context=context,
            recipients=[owner_email],
        )

