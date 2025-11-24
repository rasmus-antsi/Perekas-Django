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
        'member': member,
        'member_name': member.get_display_name(),
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


def send_admin_family_created_notification(request, family):
    """
    Send notification email to info@perekas.ee when a new family is created.
    This helps track how many families are using the app.
    """
    admin_email = 'info@perekas.ee'
    
    # Get family statistics
    owner = family.owner
    member_count = family.members.count()
    total_users = member_count + 1  # owner + members
    
    context = {
        'family': family,
        'owner': owner,
        'owner_name': owner.get_display_name(),
        'owner_email': owner.email if owner.email else 'Pole e-posti aadressi',
        'owner_role': owner.get_role_display() if hasattr(owner, 'get_role_display') else '',
        'member_count': member_count,
        'total_users': total_users,
        'join_code': family.join_code,
        'created_at': family.created_at,
        'family_url': request.build_absolute_uri(reverse('a_dashboard:dashboard')),
    }
    
    _send_branded_email(
        subject=f"[Perekas] Uus pere loodud: {family.name}",
        template_name='email/admin_family_created.html',
        context=context,
        recipients=[admin_email],
    )

