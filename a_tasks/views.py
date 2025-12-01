import itertools
import json
import re
from datetime import datetime, timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.shortcuts import redirect, render
from django.utils import timezone
from django.utils.dateparse import parse_date
from django.utils.safestring import mark_safe

from a_family.models import Family, User
from a_family.emails import send_task_completed_notification, send_task_approved_notification
from a_subscription.utils import check_subscription_limit, increment_usage

from .models import Task


def _get_family_for_user(user):
    family = None
    if hasattr(user, "families"):
        family = user.families.first()
    if family is None:
        family = Family.objects.filter(owner=user).first()
    return family


def _ensure_user_role(user, default_role=User.ROLE_CHILD):
    """Ensure user has a role set, defaulting to the provided role if not set"""
    if not user.role:
        user.role = default_role
        user.save(update_fields=['role'])
    return user


def _parse_task_text(text, family):
    """
    Parse natural language task text to extract task details.
    
    Patterns:
    - @name or @username - Assign to family member
    - !low, !medium, !high - Set priority
    - +50 or +points - Set points value
    - *daily, *weekly, *monthly - Set recurring frequency
    - Date keywords: today, tomorrow, next week, Monday, etc.
    - Date format: ^2024-12-25 for specific dates
    
    Returns dict with: name, assigned_to_id, priority, points, due_date, recurring
    """
    if not text or not text.strip():
        return None
    
    text = text.strip()
    parsed = {
        'name': '',
        'assigned_to_id': None,
        'priority': Task.PRIORITY_MEDIUM,  # Default to medium
        'points': 25,  # Default points
        'due_date': None,
        'recurring': None,
    }
    
    # Extract @mentions (assignment)
    mention_pattern = r'@(\w+)'
    mentions = re.findall(mention_pattern, text, re.IGNORECASE)
    if mentions:
        mention_name = mentions[0].lower()
        # Try to find family member by display name or username
        family_members = list(family.members.all())
        if family.owner:
            family_members.append(family.owner)
        
        # Handle "everyone" special case
        if mention_name == 'everyone' or mention_name == 'kõik':
            parsed['assigned_to_id'] = None  # None means open task
        else:
            # Try to find family member by display name or username
            for member in family_members:
                display_name = member.get_display_name().lower()
                username = (member.username or '').lower()
                first_name = (member.first_name or '').lower()
                
                if (mention_name in display_name or 
                    mention_name == username or 
                    mention_name == first_name):
                    parsed['assigned_to_id'] = member.id
                    break
        
        # Remove @mentions from text
        text = re.sub(mention_pattern, '', text, flags=re.IGNORECASE).strip()
    
    # Extract priority (!low, !medium, !high)
    priority_pattern = r'!(low|medium|high|madal|keskmine|kõrge)'
    priority_match = re.search(priority_pattern, text, re.IGNORECASE)
    if priority_match:
        priority_str = priority_match.group(1).lower()
        if priority_str in ['high', 'kõrge']:
            parsed['priority'] = Task.PRIORITY_HIGH
        elif priority_str in ['low', 'madal']:
            parsed['priority'] = Task.PRIORITY_LOW
        else:
            parsed['priority'] = Task.PRIORITY_MEDIUM
        
        text = re.sub(priority_pattern, '', text, flags=re.IGNORECASE).strip()
    
    # Extract points (+50, +points)
    points_pattern = r'\+(\d+)'
    points_match = re.search(points_pattern, text)
    if points_match:
        parsed['points'] = int(points_match.group(1))
        text = re.sub(points_pattern, '', text).strip()
    
    # Extract recurring (*daily, *weekly, *monthly)
    recurring_pattern = r'\*(daily|weekly|monthly|päevaselt|nädalaselt|kuus)'
    recurring_match = re.search(recurring_pattern, text, re.IGNORECASE)
    if recurring_match:
        recurring_str = recurring_match.group(1).lower()
        if recurring_str in ['daily', 'päevaselt']:
            parsed['recurring'] = 'daily'
        elif recurring_str in ['weekly', 'nädalaselt']:
            parsed['recurring'] = 'weekly'
        elif recurring_str in ['monthly', 'kuus']:
            parsed['recurring'] = 'monthly'
        
        text = re.sub(recurring_pattern, '', text, flags=re.IGNORECASE).strip()
    
    # Extract dates
    today = timezone.localdate()
    now = timezone.now()
    
    # Specific date format: ^2024-12-25
    date_format_pattern = r'\^(\d{4}-\d{2}-\d{2})'
    date_format_match = re.search(date_format_pattern, text)
    if date_format_match:
        try:
            parsed['due_date'] = parse_date(date_format_match.group(1))
            text = re.sub(date_format_pattern, '', text).strip()
        except (ValueError, TypeError):
            pass
    
    # Date keywords (case-insensitive)
    date_keywords = {
        'today': today,
        'täna': today,
        'tomorrow': today + timedelta(days=1),
        'homme': today + timedelta(days=1),
        'next week': today + timedelta(days=7),
        'järgmine nädal': today + timedelta(days=7),
        'next month': today + timedelta(days=30),
        'järgmine kuu': today + timedelta(days=30),
    }
    
    # Weekday names (Estonian and English)
    # Monday=0, Tuesday=1, ..., Sunday=6
    weekdays_est = ['esmaspäev', 'teisipäev', 'kolmapäev', 'neljapäev', 'reede', 'laupäev', 'pühapäev']
    weekdays_en = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']
    weekdays_est_short = ['esmasp', 'teisip', 'kolmap', 'neljap', 'reede', 'laup', 'pühap']
    
    for keyword, date_value in date_keywords.items():
        if keyword.lower() in text.lower():
            parsed['due_date'] = date_value
            # Remove keyword from text (case-insensitive)
            text = re.sub(re.escape(keyword), '', text, flags=re.IGNORECASE).strip()
            break
    
    # Check for weekday names
    text_lower = text.lower()
    all_weekdays = weekdays_est + weekdays_en + weekdays_est_short
    for i, weekday in enumerate(all_weekdays):
        if weekday in text_lower:
            # Find next occurrence of this weekday
            # Map to 0-6 (Monday-Sunday)
            weekday_index = i % 7
            days_ahead = weekday_index - today.weekday()
            if days_ahead <= 0:  # Target day already happened this week
                days_ahead += 7
            parsed['due_date'] = today + timedelta(days=days_ahead)
            text = re.sub(weekday, '', text, flags=re.IGNORECASE).strip()
            break
    
    # Clean up text: remove extra spaces, trim
    parsed['name'] = ' '.join(text.split())
    
    return parsed


@login_required
def index(request):
    user = request.user
    family = _get_family_for_user(user)

    # Redirect to onboarding if user doesn't have a family
    if not family:
        messages.info(request, "Perega liitumiseks või uue pere loomiseks palun täida pere andmed.")
        return redirect('a_family:onboarding')

    # Set default role for owner if not set
    if family and family.owner_id == user.id and not user.role:
        user.role = User.ROLE_PARENT
        user.save(update_fields=['role'])

    role = user.role or (User.ROLE_PARENT if family and family.owner_id == user.id else None)
    is_parent = role == User.ROLE_PARENT
    is_child = role == User.ROLE_CHILD

    if request.method == "POST" and family:
        action = request.POST.get("action")
        task_id = request.POST.get("task_id")

        def _get_task():
            if not task_id:
                return None
            return Task.objects.filter(family=family, id=task_id).select_related("assigned_to").first()

        if action == "create" and is_parent:
            # Check if this is a quick add (task_text) or modal form (name)
            task_text = request.POST.get("task_text", "").strip()
            name = request.POST.get("name", "").strip()
            
            # Quick add form uses task_text, modal form uses name
            if task_text:
                # Parse natural language
                parsed = _parse_task_text(task_text, family)
                if not parsed or not parsed['name']:
                    messages.error(request, "Palun sisesta ülesande nimi.")
                    return redirect("a_tasks:index")
                
                name = parsed['name']
                description = ""
                assigned_id = parsed['assigned_to_id']
                due = parsed['due_date']
                priority = parsed['priority']
                points_value = parsed['points']
                recurring = parsed['recurring']
            else:
                # Modal form (backward compatibility)
                description = request.POST.get("description", "").strip()
                assigned_id = request.POST.get("assigned_to")
                due = parse_date(request.POST.get("due_date") or "")
                priority = request.POST.get("priority")
                points_raw = request.POST.get("points", "0")
                recurring = None

            if name:
                # Check subscription limit before creating
                can_create, current_count, limit, tier = check_subscription_limit(family, 'tasks', 1)
                if not can_create:
                    messages.error(
                        request,
                        f"Oled jõudnud oma kuise ülesandepiirini ({limit} ülesannet). "
                        f"Oled sel kuul loonud {current_count} ülesannet. "
                        f"Palun uuenda tellimust, et luua rohkem ülesandeid."
                    )
                    return redirect("a_tasks:index")

                if not task_text:  # Only parse if from modal form
                    try:
                        priority_value = int(priority)
                    except (TypeError, ValueError):
                        priority_value = Task.PRIORITY_LOW

                    try:
                        points_value = max(0, int(points_raw))
                    except (TypeError, ValueError):
                        points_value = 0
                else:
                    priority_value = priority
                    # points_value already set from parsed dict

                assigned_user = None
                if assigned_id:
                    assigned_user = family.members.filter(id=assigned_id).first()
                    if not assigned_user and str(family.owner_id) == str(assigned_id):
                        assigned_user = family.owner

                task = Task.objects.create(
                    name=name,
                    description=description,
                    family=family,
                    assigned_to=assigned_user,
                    created_by=user,
                    due_date=due,
                    priority=priority_value,
                    points=points_value,
                )
                
                # Handle recurring tasks
                if recurring:
                    from .models import TaskRecurrence
                    next_occurrence = timezone.now()
                    if recurring == 'daily':
                        next_occurrence = timezone.now() + timedelta(days=1)
                    elif recurring == 'weekly':
                        next_occurrence = timezone.now() + timedelta(days=7)
                    elif recurring == 'monthly':
                        next_occurrence = timezone.now() + timedelta(days=30)
                    
                    TaskRecurrence.objects.create(
                        task=task,
                        frequency=recurring,
                        next_occurrence=next_occurrence,
                    )
                
                # Increment usage counter
                increment_usage(family, 'tasks', 1)

        elif action == "update" and is_parent:
            task = _get_task()
            if task:
                previous_points = task.points
                previous_assigned = task.assigned_to

                task.name = request.POST.get("name", task.name).strip() or task.name
                task.description = request.POST.get("description", task.description).strip()

                assigned_id = request.POST.get("assigned_to")
                assignment_changed = False
                if assigned_id:
                    new_assigned = family.members.filter(id=assigned_id).first()
                    if not new_assigned and str(family.owner_id) == str(assigned_id):
                        new_assigned = family.owner
                    if task.assigned_to_id != (new_assigned.id if new_assigned else None):
                        assignment_changed = True
                    task.assigned_to = new_assigned
                else:
                    if task.assigned_to is not None:
                        assignment_changed = True
                    task.assigned_to = None

                # Clear started_at if assignment changed
                if assignment_changed:
                    task.started_at = None

                due = parse_date(request.POST.get("due_date") or "")
                task.due_date = due

                try:
                    task.priority = int(request.POST.get("priority", task.priority))
                except (TypeError, ValueError):
                    pass

                try:
                    task.points = max(0, int(request.POST.get("points", task.points)))
                except (TypeError, ValueError):
                    pass

                update_fields = ["name", "description", "assigned_to", "due_date", "priority", "points"]
                if assignment_changed:
                    update_fields.append("started_at")
                task.save(update_fields=update_fields)

                if task.approved:
                    if previous_assigned:
                        previous_assigned.points = max(0, previous_assigned.points - previous_points)
                        previous_assigned.save(update_fields=["points"])
                    current_assignee = task.assigned_to or task.completed_by
                    if current_assignee:
                        diff = task.points
                        if previous_assigned and previous_assigned.id == current_assignee.id:
                            diff = task.points - previous_points
                        if diff != 0:
                            current_assignee.points = max(0, current_assignee.points + diff)
                            current_assignee.save(update_fields=["points"])

        elif action == "delete" and is_parent:
            task = _get_task()
            if task:
                task.delete()

        elif action == "start" and is_child:
            task = _get_task()
            if not task:
                messages.error(request, "Midagi läks valesti. Kui probleem püsib, palun võta ühendust tugiteenusega: tugi@perekas.ee")
            elif task.completed:
                messages.warning(request, "See ülesanne on juba täidetud.")
            elif task.is_in_progress:
                messages.warning(request, "See ülesanne on juba teise lapse poolt alustatud.")
            elif task.assigned_to and task.assigned_to_id != user.id:
                messages.warning(request, "See ülesanne on määratud teisele lapsele.")
            else:
                task.assigned_to = user
                task.started_at = timezone.now()
                task.save(update_fields=["assigned_to", "started_at"])
                messages.success(request, f"Ülesanne '{task.name}' alustatud!")

        elif action == "cancel" and is_child:
            task = _get_task()
            if not task:
                messages.error(request, "Midagi läks valesti. Kui probleem püsib, palun võta ühendust tugiteenusega: tugi@perekas.ee")
            elif task.completed:
                messages.warning(request, "See ülesanne on juba täidetud.")
            elif not task.is_in_progress or task.assigned_to_id != user.id:
                messages.warning(request, "Sa saad tühistada ainult enda alustatud ülesandeid.")
            else:
                task.assigned_to = None
                task.started_at = None
                task.save(update_fields=["assigned_to", "started_at"])
                messages.success(request, f"Ülesanne '{task.name}' tühistatud.")

        elif action == "complete" and is_child:
            task = _get_task()
            if not task:
                messages.error(request, "Midagi läks valesti. Kui probleem püsib, palun võta ühendust tugiteenusega: tugi@perekas.ee")
            elif task.completed:
                messages.warning(request, "See ülesanne on juba täidetud.")
            elif not task.is_in_progress or task.assigned_to_id != user.id:
                messages.warning(request, "Sa saad täita ainult enda alustatud ülesandeid.")
            else:
                task.completed = True
                task.completed_by = user
                task.completed_at = timezone.now()
                task.approved = False
                task.approved_by = None
                task.approved_at = None
                # Keep started_at for history, but task is no longer in progress
                task.save(update_fields=["completed", "completed_by", "completed_at", "approved", "approved_by", "approved_at"])
                # Send notification email
                try:
                    send_task_completed_notification(request, task)
                except Exception as e:
                    import logging
                    logger = logging.getLogger(__name__)
                    logger.warning(f"Failed to send task completed notification: {e}", exc_info=True)

        elif action == "reopen" and is_parent:
            task = _get_task()
            if not task:
                messages.error(request, "Midagi läks valesti. Kui probleem püsib, palun võta ühendust tugiteenusega: tugi@perekas.ee")
            elif not task.completed:
                messages.warning(request, "See ülesanne pole täidetud.")
            else:
                # Use transaction to ensure atomicity
                try:
                    with transaction.atomic():
                        if task.approved:
                            assignee = task.assigned_to or task.completed_by
                            if assignee:
                                # Refresh assignee from DB to avoid race conditions
                                assignee = User.objects.select_for_update().get(id=assignee.id)
                                assignee.points = max(0, assignee.points - task.points)
                                assignee.save(update_fields=["points"])
                        
                        task.completed = False
                        task.completed_by = None
                        task.completed_at = None
                        task.approved = False
                        task.approved_by = None
                        task.approved_at = None
                        task.started_at = None
                        task.assigned_to = None
                        task.save(update_fields=["completed", "completed_by", "completed_at", "approved", "approved_by", "approved_at", "started_at", "assigned_to"])
                        messages.success(request, f"Ülesanne '{task.name}' avatud uuesti.")
                except Exception as e:
                    messages.error(request, "Midagi läks valesti. Kui probleem püsib, palun võta ühendust tugiteenusega: tugi@perekas.ee")

        elif action == "approve" and is_parent:
            task = _get_task()
            if not task:
                messages.error(request, "Midagi läks valesti. Kui probleem püsib, palun võta ühendust tugiteenusega: tugi@perekas.ee")
            elif not task.completed:
                messages.error(request, "Saab kinnitada ainult täidetud ülesandeid.")
            elif task.approved:
                messages.warning(request, "See ülesanne on juba kinnitatud.")
            else:
                # Use transaction to ensure atomicity
                try:
                    with transaction.atomic():
                        assignee = task.assigned_to or task.completed_by
                        if not assignee:
                            messages.error(request, "Ülesandel pole määratud täitjat.")
                        else:
                            # Refresh assignee from DB to avoid race conditions
                            assignee = User.objects.select_for_update().get(id=assignee.id)
                            
                            task.approved = True
                            task.approved_by = user
                            task.approved_at = timezone.now()
                            task.save(update_fields=["approved", "approved_by", "approved_at"])

                            assignee.points += task.points
                            assignee.save(update_fields=["points"])
                            messages.success(request, f"Ülesanne '{task.name}' kinnitatud. {task.points} punkti lisatud.")
                            
                            # Send notification email
                            try:
                                send_task_approved_notification(request, task)
                            except Exception as e:
                                import logging
                                logger = logging.getLogger(__name__)
                                logger.warning(f"Failed to send task approved notification: {e}", exc_info=True)
                except Exception as e:
                    messages.error(request, "Midagi läks valesti. Kui probleem püsib, palun võta ühendust tugiteenusega: tugi@perekas.ee")

        elif action == "unapprove" and is_parent:
            task = _get_task()
            if not task:
                messages.error(request, "Midagi läks valesti. Kui probleem püsib, palun võta ühendust tugiteenusega: tugi@perekas.ee")
            elif not task.approved:
                messages.warning(request, "See ülesanne pole kinnitatud.")
            else:
                # Use transaction to ensure atomicity
                try:
                    with transaction.atomic():
                        assignee = task.assigned_to or task.completed_by
                        if assignee:
                            # Refresh assignee from DB to avoid race conditions
                            assignee = User.objects.select_for_update().get(id=assignee.id)
                            assignee.points = max(0, assignee.points - task.points)
                            assignee.save(update_fields=["points"])

                        task.approved = False
                        task.approved_by = None
                        task.approved_at = None
                        task.save(update_fields=["approved", "approved_by", "approved_at"])
                        messages.success(request, f"Ülesande '{task.name}' kinnitamine tühistatud.")
                except Exception as e:
                    messages.error(request, "Midagi läks valesti. Kui probleem püsib, palun võta ühendust tugiteenusega: tugi@perekas.ee")

        return redirect("a_tasks:index")

    if family:
        tasks_qs = Task.objects.filter(family=family).select_related(
            "assigned_to",
            "created_by",
            "completed_by",
            "approved_by",
        )
        active_tasks = list(tasks_qs.filter(completed=False))
        pending_tasks = list(tasks_qs.filter(completed=True, approved=False))
        approved_tasks = list(tasks_qs.filter(approved=True))

        for task in itertools.chain(active_tasks, pending_tasks, approved_tasks):
            if is_child:
                # Can start if: not completed, not in progress, and (not assigned or assigned to this user)
                task.can_child_start = (
                    not task.completed and
                    not task.is_in_progress and
                    (task.assigned_to is None or task.assigned_to_id == user.id)
                )
                # Can complete if: in progress and assigned to this user
                task.can_child_complete = task.is_in_progress and task.assigned_to_id == user.id
                # Can cancel if: in progress and assigned to this user
                task.can_child_cancel = task.is_in_progress and task.assigned_to_id == user.id
            else:
                task.can_child_start = False
                task.can_child_complete = False
                task.can_child_cancel = False

        # Only show children in the task assignment dropdown (not parents)
        family_members_qs = family.members.filter(role=User.ROLE_CHILD)
        member_ids = set(family_members_qs.values_list("id", flat=True))
        # Also check owner if they're a child
        if family.owner and family.owner.role == User.ROLE_CHILD:
            if family.owner_id not in member_ids:
                family_members = list(family_members_qs) + [family.owner]
            else:
                family_members = list(family_members_qs)
        else:
            family_members = list(family_members_qs)
    else:
        active_tasks = []
        pending_tasks = []
        approved_tasks = []
        family_members = []

    # Prepare family members data for autocomplete (first name + username format)
    family_members_data = []
    for member in family_members:
        name_parts = []
        if member.first_name:
            name_parts.append(member.first_name)
        if member.username:
            name_parts.append(f"@{member.username}")
        display_text = " ".join(name_parts) if name_parts else member.get_display_name()
        family_members_data.append({
            'id': member.id,
            'first_name': member.first_name or '',
            'username': member.username or '',
            'display_text': display_text,
            'search_text': f"{member.first_name or ''} {member.username or ''}".strip().lower(),
        })
    
    # Convert to JSON string for template
    family_members_json = mark_safe(json.dumps(family_members_data))
    
    context = {
        "family": family,
        "role": role,
        "is_parent": is_parent,
        "is_child": is_child,
        "has_family": family is not None,
        "family_members": family_members,
        "family_members_data": family_members_json,  # JSON string for autocomplete
        "active_tasks": active_tasks,
        "pending_tasks": pending_tasks,
        "approved_tasks": approved_tasks,
    }
    return render(request, "a_tasks/index.html", context)