import logging
import threading

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template import TemplateDoesNotExist
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils.html import strip_tags

from a_family.models import User


logger = logging.getLogger(__name__)


def _get_logo_url(request):
    """Generate absolute URL for the logo image."""
    return request.build_absolute_uri('/static/logos/perekas-logo.png')


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
        'logo_url': _get_logo_url(request),
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
        'logo_url': _get_logo_url(request),
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
        'logo_url': _get_logo_url(request),
    }
    
    _send_branded_email(
        subject=f"[Perekas] Uus pere loodud: {family.name}",
        template_name='email/admin_family_created.html',
        context=context,
        recipients=[admin_email],
    )


def _get_users_to_notify(family, preference_key):
    """
    Get list of users in the family who have email and have the specified notification preference enabled.
    
    Args:
        family: Family instance
        preference_key: Key from notification_preferences (e.g., 'task_updates', 'reward_updates')
    
    Returns:
        List of email addresses to notify
    """
    recipients = []
    all_members = list(family.members.all()) + [family.owner]
    
    for user in all_members:
        if not user.email:
            continue
        
        # Check notification preferences (default to True if not set)
        prefs = user.notification_preferences or {}
        if prefs.get(preference_key, True):  # Default to True if not set
            recipients.append(user.email)
    
    return recipients


def send_task_completed_notification(request, task):
    """
    Send notification email when a task is completed and needs approval.
    Notifies only parents in the family who have task_updates enabled.
    """
    if not task.family:
        return
    
    # Get only parents (owners) in the family who have email and task_updates enabled
    recipients = []
    all_members = list(task.family.members.all()) + [task.family.owner]
    
    for user in all_members:
        # Only notify parents
        if user.role != User.ROLE_PARENT:
            continue
        
        if not user.email:
            continue
        
        # Check notification preferences (default to True if not set)
        prefs = user.notification_preferences or {}
        if prefs.get('task_updates', True):  # Default to True if not set
            recipients.append(user.email)
    
    if not recipients:
        return
    
    dashboard_url = request.build_absolute_uri(reverse('a_dashboard:dashboard'))
    tasks_url = request.build_absolute_uri(reverse('a_tasks:index'))
    
    context = {
        'task': task,
        'family': task.family,
        'completed_by': task.completed_by,
        'completed_by_name': task.completed_by.get_display_name() if task.completed_by else 'Keegi',
        'dashboard_url': dashboard_url,
        'tasks_url': tasks_url,
        'logo_url': _get_logo_url(request),
    }
    
    _send_branded_email(
        subject=f"Ülesanne täidetud: {task.name}",
        template_name='email/task_completed.html',
        context=context,
        recipients=recipients,
    )


def send_task_approved_notification(request, task):
    """
    Send notification email when a task is approved.
    Notifies the assignee if they have task_updates enabled.
    """
    assignee = task.assigned_to or task.completed_by
    if not assignee or not assignee.email:
        return
    
    prefs = assignee.notification_preferences or {}
    if not prefs.get('task_updates', True):  # Default to True
        return
    
    dashboard_url = request.build_absolute_uri(reverse('a_dashboard:dashboard'))
    tasks_url = request.build_absolute_uri(reverse('a_tasks:index'))
    
    context = {
        'task': task,
        'family': task.family,
        'assignee': assignee,
        'approved_by': task.approved_by,
        'approved_by_name': task.approved_by.get_display_name() if task.approved_by else 'Keegi',
        'dashboard_url': dashboard_url,
        'tasks_url': tasks_url,
        'logo_url': _get_logo_url(request),
    }
    
    _send_branded_email(
        subject=f"Ülesanne kinnitatud: {task.name}",
        template_name='email/task_approved.html',
        context=context,
        recipients=[assignee.email],
    )


# Removed send_reward_created_notification - we only notify when rewards are claimed/taken


def send_reward_claimed_notification(request, reward):
    """
    Send notification email when a reward is claimed.
    Notifies all family members who have reward_updates enabled.
    """
    if not reward.family:
        return
    
    recipients = _get_users_to_notify(reward.family, 'reward_updates')
    if not recipients:
        return
    
    dashboard_url = request.build_absolute_uri(reverse('a_dashboard:dashboard'))
    rewards_url = request.build_absolute_uri(reverse('a_rewards:index'))
    
    context = {
        'reward': reward,
        'family': reward.family,
        'claimed_by': reward.claimed_by,
        'claimed_by_name': reward.claimed_by.get_display_name() if reward.claimed_by else 'Keegi',
        'dashboard_url': dashboard_url,
        'rewards_url': rewards_url,
        'logo_url': _get_logo_url(request),
    }
    
    _send_branded_email(
        subject=f"Preemia lunastatud: {reward.name}",
        template_name='email/reward_claimed.html',
        context=context,
        recipients=recipients,
    )


def send_shopping_item_added_notification(request, item):
    """
    Send notification email when a shopping list item is added.
    Notifies all family members who have shopping_updates enabled.
    """
    if not item.family:
        return
    
    recipients = _get_users_to_notify(item.family, 'shopping_updates')
    if not recipients:
        return
    
    dashboard_url = request.build_absolute_uri(reverse('a_dashboard:dashboard'))
    shopping_url = request.build_absolute_uri(reverse('a_shopping:index'))
    
    context = {
        'item': item,
        'family': item.family,
        'added_by': item.added_by,
        'added_by_name': item.added_by.get_display_name() if item.added_by else 'Keegi',
        'dashboard_url': dashboard_url,
        'shopping_url': shopping_url,
        'logo_url': _get_logo_url(request),
    }
    
    _send_branded_email(
        subject=f"Ostunimekirja lisatud: {item.name}",
        template_name='email/shopping_item_added.html',
        context=context,
        recipients=recipients,
    )


def send_welcome_email(request, user):
    """
    Send welcome email to new users after signup.
    Only sends if user has an email address.
    """
    if not user.email:
        return
    
    dashboard_url = request.build_absolute_uri(reverse('a_dashboard:dashboard'))
    
    context = {
        'user': user,
        'user_name': user.get_display_name(),
        'dashboard_url': dashboard_url,
        'logo_url': _get_logo_url(request),
    }
    
    _send_branded_email(
        subject="Tere tulemast Perekasse!",
        template_name='email/welcome.html',
        context=context,
        recipients=[user.email],
    )


def send_bulk_email(template, users, base_url=None):
    """
    Send email using an EmailTemplate to a list of users.
    
    Args:
        template: EmailTemplate instance with subject and body_html
        users: QuerySet or list of User instances
        base_url: Base URL for building absolute URLs (e.g., 'https://perekas.ee')
    
    Returns:
        tuple: (sent_count, skipped_count)
    """
    sent_count = 0
    skipped_count = 0
    
    # Default base URL
    if not base_url:
        base_url = 'https://perekas.ee'
    
    logo_url = f"{base_url}/static/logos/perekas-logo.png"
    
    for user in users:
        if not user.email:
            skipped_count += 1
            continue
        
        context = {
            'user': user,
            'user_name': user.get_display_name(),
            'base_url': base_url,
            'logo_url': logo_url,
            'body_content': template.body_html,
        }
        
        _send_branded_email(
            subject=template.subject,
            template_name='email/bulk_template.html',
            context=context,
            recipients=[user.email],
        )
        sent_count += 1
    
    return sent_count, skipped_count

