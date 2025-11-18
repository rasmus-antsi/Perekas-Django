import itertools

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.shortcuts import redirect, render
from django.utils import timezone
from django.utils.dateparse import parse_date

from a_family.models import Family, User
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


@login_required
def index(request):
    user = request.user
    family = _get_family_for_user(user)

    # Redirect to onboarding if user doesn't have a family
    if not family:
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
            name = request.POST.get("name", "").strip()
            description = request.POST.get("description", "").strip()
            assigned_id = request.POST.get("assigned_to")
            due = parse_date(request.POST.get("due_date") or "")
            priority = request.POST.get("priority")
            points_raw = request.POST.get("points", "0")

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

                try:
                    priority_value = int(priority)
                except (TypeError, ValueError):
                    priority_value = Task.PRIORITY_LOW

                try:
                    points_value = max(0, int(points_raw))
                except (TypeError, ValueError):
                    points_value = 0

                assigned_user = None
                if assigned_id:
                    assigned_user = family.members.filter(id=assigned_id).first()
                    if not assigned_user and str(family.owner_id) == str(assigned_id):
                        assigned_user = family.owner

                Task.objects.create(
                    name=name,
                    description=description,
                    family=family,
                    assigned_to=assigned_user,
                    created_by=user,
                    due_date=due,
                    priority=priority_value,
                    points=points_value,
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
                if assigned_id:
                    new_assigned = family.members.filter(id=assigned_id).first()
                    if not new_assigned and str(family.owner_id) == str(assigned_id):
                        new_assigned = family.owner
                    task.assigned_to = new_assigned
                else:
                    task.assigned_to = None

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

                task.save()

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

        elif action == "complete" and is_child:
            task = _get_task()
            if task and task.assigned_to_id == user.id and not task.completed:
                task.completed = True
                task.completed_by = user
                task.completed_at = timezone.now()
                task.approved = False
                task.approved_by = None
                task.approved_at = None
                task.save(update_fields=["completed", "completed_by", "completed_at", "approved", "approved_by", "approved_at"])
            elif task and task.assigned_to is None and not task.completed:
                task.assigned_to = user
                task.completed = True
                task.completed_by = user
                task.completed_at = timezone.now()
                task.approved = False
                task.approved_by = None
                task.approved_at = None
                task.save(update_fields=["assigned_to", "completed", "completed_by", "completed_at", "approved", "approved_by", "approved_at"])

        elif action == "reopen" and is_parent:
            task = _get_task()
            if not task:
                messages.error(request, "Ülesannet ei leitud. See võib olla kustutatud.")
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
                        task.save(update_fields=["completed", "completed_by", "completed_at", "approved", "approved_by", "approved_at"])
                        messages.success(request, f"Ülesanne '{task.name}' avatud uuesti.")
                except Exception as e:
                    messages.error(request, f"Ülesande avamisel tekkis viga: {str(e)}")

        elif action == "approve" and is_parent:
            task = _get_task()
            if not task:
                messages.error(request, "Ülesannet ei leitud. See võib olla kustutatud.")
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
                except Exception as e:
                    messages.error(request, f"Ülesande kinnitamisel tekkis viga: {str(e)}")

        elif action == "unapprove" and is_parent:
            task = _get_task()
            if not task:
                messages.error(request, "Ülesannet ei leitud. See võib olla kustutatud.")
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
                    messages.error(request, f"Ülesande kinnituse tühistamisel tekkis viga: {str(e)}")

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
            task.can_child_complete = is_child and (task.assigned_to_id is None or task.assigned_to_id == user.id)

        family_members_qs = family.members.all()
        member_ids = set(family_members_qs.values_list("id", flat=True))
        if family.owner_id not in member_ids:
            from django.contrib.auth import get_user_model

            UserModel = get_user_model()
            owner_qs = UserModel.objects.filter(id=family.owner_id)
            family_members = list(family_members_qs) + list(owner_qs)
        else:
            family_members = list(family_members_qs)
    else:
        active_tasks = []
        pending_tasks = []
        approved_tasks = []
        family_members = []

    context = {
        "family": family,
        "role": role,
        "is_parent": is_parent,
        "is_child": is_child,
        "has_family": family is not None,
        "family_members": family_members,
        "active_tasks": active_tasks,
        "pending_tasks": pending_tasks,
        "approved_tasks": approved_tasks,
    }
    return render(request, "a_tasks/index.html", context)