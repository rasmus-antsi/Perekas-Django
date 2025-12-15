import json
import time
import uuid
from django.contrib.auth import authenticate
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.utils import timezone
from django.db import transaction

from a_family.models import User, Family
from a_family.utils import get_family_for_user
from a_tasks.models import Task
from a_rewards.models import Reward
from a_shopping.models import ShoppingListItem
from a_subscription.utils import check_subscription_limit, increment_usage, has_shopping_list_access
from .meta_capi import (
    MetaCapiConfigError,
    MetaCapiSendError,
    build_event_payload,
    build_user_data,
    default_event_id,
    default_event_time,
    send_events_to_meta,
)


def _get_user_from_request(request):
    """Get authenticated user from request"""
    if not request.user.is_authenticated:
        return None
    return request.user


def _json_response(data, status=200):
    """Helper to return JSON response"""
    return JsonResponse(data, status=status, safe=False)

def _client_ip(request):
    forwarded = request.META.get('HTTP_X_FORWARDED_FOR')
    if forwarded:
        return forwarded.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR')


ALLOWED_META_EVENTS = {"Purchase", "ViewContent", "Lead", "CompleteRegistration"}


@csrf_exempt
@require_http_methods(["POST"])
def meta_events(request):
    """Accept Meta CAPI events (server-side) and forward to Meta."""
    try:
        payload = json.loads(request.body)
    except json.JSONDecodeError:
        return _json_response({'error': 'Invalid JSON'}, status=400)

    event_name = payload.get('event_name')
    if event_name not in ALLOWED_META_EVENTS:
        return _json_response({'error': 'Unsupported event_name'}, status=400)

    event_time = default_event_time(payload.get('event_time'))
    event_source_url = payload.get('event_source_url')
    if not event_source_url:
        return _json_response({'error': 'event_source_url is required'}, status=400)

    action_source = payload.get('action_source', 'website')
    event_id = payload.get('event_id') or default_event_id()
    email = payload.get('email')
    currency = payload.get('currency')
    value = payload.get('value')
    attribution_data = payload.get('attribution_data')
    original_event_data = payload.get('original_event_data')
    test_event_code = payload.get('test_event_code')

    client_ip = _client_ip(request)
    client_user_agent = request.META.get('HTTP_USER_AGENT', '')
    user_data = build_user_data(email, client_ip, client_user_agent)

    custom_data = payload.get('custom_data') or {}
    if event_name == 'Purchase':
        if not currency or value is None:
            return _json_response({'error': 'currency and value are required for Purchase'}, status=400)
        custom_data.update({'currency': currency, 'value': value})

    event_payload = build_event_payload(
        event_name=event_name,
        event_time=event_time,
        event_source_url=event_source_url,
        action_source=action_source,
        event_id=event_id,
        user_data=user_data,
        custom_data=custom_data or None,
        attribution_data=attribution_data,
        original_event_data=original_event_data,
    )

    try:
        meta_response = send_events_to_meta([event_payload], test_event_code=test_event_code)
    except MetaCapiConfigError as exc:
        return _json_response({'error': str(exc)}, status=500)
    except MetaCapiSendError as exc:
        return _json_response({'error': 'Meta CAPI error', 'details': getattr(exc, 'args', [''])[0]}, status=502)
    except Exception as exc:
        return _json_response({'error': str(exc)}, status=500)

    return _json_response({
        'event_id': event_id,
        'events_received': meta_response.get('events_received'),
        'fbtrace_id': meta_response.get('fbtrace_id'),
        'messages': meta_response.get('messages'),
    })


@csrf_exempt
@require_http_methods(["POST"])
def login(request):
    """Authenticate user and return user data"""
    try:
        data = json.loads(request.body)
        username = data.get('username', '').strip()
        password = data.get('password', '')
        
        if not username or not password:
            return _json_response({'error': 'Username and password required'}, status=400)
        
        user = authenticate(request, username=username, password=password)
        if user is None:
            return _json_response({'error': 'Invalid credentials'}, status=401)
        
        if not user.is_active:
            return _json_response({'error': 'Account is disabled'}, status=403)
        
        # Create session
        from django.contrib.auth import login as django_login
        django_login(request, user)
        
        family = get_family_for_user(user)
        
        family_data = None
        if family:
            members = list(family.members.all())
            if family.owner not in members:
                members.append(family.owner)
            
            members_data = []
            for member in members:
                members_data.append({
                    'id': member.id,
                    'username': member.username,
                    'email': member.email,
                    'first_name': member.first_name,
                    'last_name': member.last_name,
                    'role': member.role,
                    'points': member.points,
                    'display_name': member.get_display_name(),
                })
            
            family_data = {
                'id': str(family.id),
                'name': family.name,
                'join_code': family.join_code,
                'owner': {
                    'id': family.owner.id,
                    'username': family.owner.username,
                    'email': family.owner.email,
                    'first_name': family.owner.first_name,
                    'last_name': family.owner.last_name,
                    'role': family.owner.role,
                    'points': family.owner.points,
                    'display_name': family.owner.get_display_name(),
                },
                'members': members_data,
                'created_at': family.created_at.isoformat(),
            }
        
        return _json_response({
            'user': {
                'id': user.id,
                'username': user.username,
                'email': user.email,
                'first_name': user.first_name,
                'last_name': user.last_name,
                'role': user.role,
                'points': user.points,
                'display_name': user.get_display_name(),
            },
            'family': family_data,
            'session_id': request.session.session_key,
        })
    except json.JSONDecodeError:
        return _json_response({'error': 'Invalid JSON'}, status=400)
    except Exception as e:
        return _json_response({'error': str(e)}, status=500)


@require_http_methods(["POST"])
def logout(request):
    """Logout user"""
    from django.contrib.auth import logout as django_logout
    django_logout(request)
    return _json_response({'message': 'Logged out successfully'})


@require_http_methods(["GET"])
def get_user(request):
    """Get current user profile"""
    user = _get_user_from_request(request)
    if not user:
        return _json_response({'error': 'Authentication required'}, status=401)
    
    family = get_family_for_user(user)
    
    family_data = None
    if family:
        members = list(family.members.all())
        if family.owner not in members:
            members.append(family.owner)
        
        members_data = []
        for member in members:
            members_data.append({
                'id': member.id,
                'username': member.username,
                'email': member.email,
                'first_name': member.first_name,
                'last_name': member.last_name,
                'role': member.role,
                'points': member.points,
                'display_name': member.get_display_name(),
            })
        
        family_data = {
            'id': str(family.id),
            'name': family.name,
            'join_code': family.join_code,
            'owner': {
                'id': family.owner.id,
                'username': family.owner.username,
                'email': family.owner.email,
                'first_name': family.owner.first_name,
                'last_name': family.owner.last_name,
                'role': family.owner.role,
                'points': family.owner.points,
                'display_name': family.owner.get_display_name(),
            },
            'members': members_data,
            'created_at': family.created_at.isoformat(),
        }
    
    return _json_response({
        'user': {
            'id': user.id,
            'username': user.username,
            'email': user.email,
            'first_name': user.first_name,
            'last_name': user.last_name,
            'role': user.role,
            'points': user.points,
            'display_name': user.get_display_name(),
            'birthdate': user.birthdate.isoformat() if user.birthdate else None,
        },
        'family': family_data,
    })


@csrf_exempt
@require_http_methods(["POST"])
def register(request):
    """Register new user and create family"""
    try:
        data = json.loads(request.body)
        username = data.get('username', '').strip()
        password = data.get('password', '')
        email = data.get('email', '').strip()
        first_name = data.get('first_name', '').strip()
        last_name = data.get('last_name', '').strip()
        role = data.get('role', User.ROLE_PARENT)
        family_name = data.get('family_name', '').strip()
        
        if not username or not password:
            return _json_response({'error': 'Username and password required'}, status=400)
        
        if User.objects.filter(username=username).exists():
            return _json_response({'error': 'Username already exists'}, status=400)
        
        if email and User.objects.filter(email=email).exists():
            return _json_response({'error': 'Email already exists'}, status=400)
        
        with transaction.atomic():
            user = User.objects.create_user(
                username=username,
                password=password,
                email=email if email else None,
                first_name=first_name,
                last_name=last_name,
                role=role,
            )
            
            # Create family if parent
            family = None
            if role == User.ROLE_PARENT and family_name:
                family = Family.objects.create(
                    name=family_name,
                    owner=user,
                )
                family.members.add(user)
            
            # Login user
            from django.contrib.auth import login as django_login
            django_login(request, user)
            
            family_data = None
            if family:
                members = list(family.members.all())
                if family.owner not in members:
                    members.append(family.owner)
                
                members_data = []
                for member in members:
                    members_data.append({
                        'id': member.id,
                        'username': member.username,
                        'email': member.email,
                        'first_name': member.first_name,
                        'last_name': member.last_name,
                        'role': member.role,
                        'points': member.points,
                        'display_name': member.get_display_name(),
                    })
                
                family_data = {
                    'id': str(family.id),
                    'name': family.name,
                    'join_code': family.join_code,
                    'owner': {
                        'id': family.owner.id,
                        'username': family.owner.username,
                        'email': family.owner.email,
                        'first_name': family.owner.first_name,
                        'last_name': family.owner.last_name,
                        'role': family.owner.role,
                        'points': family.owner.points,
                        'display_name': family.owner.get_display_name(),
                    },
                    'members': members_data,
                    'created_at': family.created_at.isoformat(),
                }
            
            return _json_response({
                'user': {
                    'id': user.id,
                    'username': user.username,
                    'email': user.email,
                    'first_name': user.first_name,
                    'last_name': user.last_name,
                    'role': user.role,
                    'points': user.points,
                    'display_name': user.get_display_name(),
                },
                'family': family_data,
            }, status=201)
    except json.JSONDecodeError:
        return _json_response({'error': 'Invalid JSON'}, status=400)
    except Exception as e:
        return _json_response({'error': str(e)}, status=500)


@require_http_methods(["GET"])
def get_tasks(request):
    """Get tasks for user's family"""
    user = _get_user_from_request(request)
    if not user:
        return _json_response({'error': 'Authentication required'}, status=401)
    
    family = get_family_for_user(user)
    if not family:
        return _json_response({'error': 'No family found'}, status=404)
    
    tasks = Task.objects.filter(family=family).select_related(
        'assigned_to', 'created_by', 'completed_by', 'approved_by'
    ).order_by('-priority', 'due_date', 'name')
    
    tasks_data = []
    for task in tasks:
        tasks_data.append({
            'id': task.id,
            'name': task.name,
            'description': task.description,
            'assigned_to': {
                'id': task.assigned_to.id,
                'display_name': task.assigned_to.get_display_name(),
            } if task.assigned_to else None,
            'created_by': {
                'id': task.created_by.id,
                'display_name': task.created_by.get_display_name(),
            },
            'completed': task.completed,
            'completed_by': {
                'id': task.completed_by.id,
                'display_name': task.completed_by.get_display_name(),
            } if task.completed_by else None,
            'approved': task.approved,
            'approved_by': {
                'id': task.approved_by.id,
                'display_name': task.approved_by.get_display_name(),
            } if task.approved_by else None,
            'due_date': task.due_date.isoformat() if task.due_date else None,
            'priority': task.priority,
            'points': task.points,
            'completed_at': task.completed_at.isoformat() if task.completed_at else None,
            'approved_at': task.approved_at.isoformat() if task.approved_at else None,
            'started_at': task.started_at.isoformat() if task.started_at else None,
            'created_at': task.created_at.isoformat(),
            'updated_at': task.updated_at.isoformat(),
            'is_in_progress': task.is_in_progress,
        })
    
    return _json_response(tasks_data)


@csrf_exempt
@require_http_methods(["POST"])
def create_task(request):
    """Create a new task"""
    user = _get_user_from_request(request)
    if not user:
        return _json_response({'error': 'Authentication required'}, status=401)
    
    if user.role != User.ROLE_PARENT:
        return _json_response({'error': 'Only parents can create tasks'}, status=403)
    
    family = get_family_for_user(user)
    if not family:
        return _json_response({'error': 'No family found'}, status=404)
    
    try:
        data = json.loads(request.body)
        name = data.get('name', '').strip()
        description = data.get('description', '').strip()
        assigned_to_id = data.get('assigned_to_id')
        due_date_str = data.get('due_date')
        priority = int(data.get('priority', Task.PRIORITY_MEDIUM))
        points = int(data.get('points', 25))
        
        if not name:
            return _json_response({'error': 'Task name required'}, status=400)
        
        # Check subscription limit
        can_create, current_count, limit, tier = check_subscription_limit(family, 'tasks', 1)
        if not can_create:
            return _json_response({
                'error': f'Task limit reached ({current_count}/{limit})',
                'limit_reached': True,
            }, status=403)
        
        assigned_to = None
        if assigned_to_id:
            assigned_to = family.members.filter(id=assigned_to_id).first()
            if not assigned_to and str(family.owner_id) == str(assigned_to_id):
                assigned_to = family.owner
        
        due_date = None
        if due_date_str:
            from django.utils.dateparse import parse_date
            due_date = parse_date(due_date_str)
        
        with transaction.atomic():
            task = Task.objects.create(
                name=name,
                description=description,
                family=family,
                assigned_to=assigned_to,
                created_by=user,
                due_date=due_date,
                priority=priority,
                points=points,
            )
            
            increment_usage(family, 'tasks', 1)
            
            return _json_response({
                'id': task.id,
                'name': task.name,
                'description': task.description,
                'assigned_to': {
                    'id': task.assigned_to.id,
                    'display_name': task.assigned_to.get_display_name(),
                } if task.assigned_to else None,
                'created_by': {
                    'id': task.created_by.id,
                    'display_name': task.created_by.get_display_name(),
                },
                'completed': task.completed,
                'approved': task.approved,
                'due_date': task.due_date.isoformat() if task.due_date else None,
                'priority': task.priority,
                'points': task.points,
                'created_at': task.created_at.isoformat(),
            }, status=201)
    except json.JSONDecodeError:
        return _json_response({'error': 'Invalid JSON'}, status=400)
    except Exception as e:
        return _json_response({'error': str(e)}, status=500)


@csrf_exempt
@require_http_methods(["PUT"])
def update_task(request, task_id):
    """Update a task"""
    user = _get_user_from_request(request)
    if not user:
        return _json_response({'error': 'Authentication required'}, status=401)
    
    if user.role != User.ROLE_PARENT:
        return _json_response({'error': 'Only parents can update tasks'}, status=403)
    
    family = get_family_for_user(user)
    if not family:
        return _json_response({'error': 'No family found'}, status=404)
    
    try:
        task = Task.objects.filter(family=family, id=task_id).first()
        if not task:
            return _json_response({'error': 'Task not found'}, status=404)
        
        data = json.loads(request.body)
        
        if 'name' in data:
            task.name = data['name'].strip()
        if 'description' in data:
            task.description = data['description'].strip()
        if 'assigned_to_id' in data:
            assigned_to_id = data['assigned_to_id']
            if assigned_to_id:
                assigned_to = family.members.filter(id=assigned_to_id).first()
                if not assigned_to and str(family.owner_id) == str(assigned_to_id):
                    assigned_to = family.owner
                task.assigned_to = assigned_to
            else:
                task.assigned_to = None
        if 'due_date' in data:
            due_date_str = data['due_date']
            if due_date_str:
                from django.utils.dateparse import parse_date
                task.due_date = parse_date(due_date_str)
            else:
                task.due_date = None
        if 'priority' in data:
            task.priority = int(data['priority'])
        if 'points' in data:
            task.points = int(data['points'])
        
        task.save()
        
        return _json_response({
            'id': task.id,
            'name': task.name,
            'description': task.description,
            'assigned_to': {
                'id': task.assigned_to.id,
                'display_name': task.assigned_to.get_display_name(),
            } if task.assigned_to else None,
            'due_date': task.due_date.isoformat() if task.due_date else None,
            'priority': task.priority,
            'points': task.points,
        })
    except json.JSONDecodeError:
        return _json_response({'error': 'Invalid JSON'}, status=400)
    except Exception as e:
        return _json_response({'error': str(e)}, status=500)


@csrf_exempt
@require_http_methods(["POST"])
def start_task(request, task_id):
    """Start working on a task"""
    user = _get_user_from_request(request)
    if not user:
        return _json_response({'error': 'Authentication required'}, status=401)
    
    if user.role != User.ROLE_CHILD:
        return _json_response({'error': 'Only children can start tasks'}, status=403)
    
    family = get_family_for_user(user)
    if not family:
        return _json_response({'error': 'No family found'}, status=404)
    
    try:
        task = Task.objects.filter(family=family, id=task_id).first()
        if not task:
            return _json_response({'error': 'Task not found'}, status=404)
        
        if task.completed:
            return _json_response({'error': 'Task already completed'}, status=400)
        
        if task.is_in_progress:
            return _json_response({'error': 'Task already in progress'}, status=400)
        
        if task.assigned_to and task.assigned_to_id != user.id:
            return _json_response({'error': 'Task assigned to another user'}, status=403)
        
        task.assigned_to = user
        task.started_at = timezone.now()
        task.save(update_fields=['assigned_to', 'started_at'])
        
        return _json_response({'message': 'Task started successfully'})
    except Exception as e:
        return _json_response({'error': str(e)}, status=500)


@csrf_exempt
@require_http_methods(["POST"])
def cancel_task(request, task_id):
    """Cancel a started task"""
    user = _get_user_from_request(request)
    if not user:
        return _json_response({'error': 'Authentication required'}, status=401)
    
    if user.role != User.ROLE_CHILD:
        return _json_response({'error': 'Only children can cancel tasks'}, status=403)
    
    family = get_family_for_user(user)
    if not family:
        return _json_response({'error': 'No family found'}, status=404)
    
    try:
        task = Task.objects.filter(family=family, id=task_id).first()
        if not task:
            return _json_response({'error': 'Task not found'}, status=404)
        
        if task.completed:
            return _json_response({'error': 'Task already completed'}, status=400)
        
        if not task.is_in_progress or task.assigned_to_id != user.id:
            return _json_response({'error': 'You can only cancel tasks you started'}, status=403)
        
        task.assigned_to = None
        task.started_at = None
        task.save(update_fields=['assigned_to', 'started_at'])
        
        return _json_response({'message': 'Task cancelled successfully'})
    except Exception as e:
        return _json_response({'error': str(e)}, status=500)


@csrf_exempt
@require_http_methods(["POST"])
def complete_task(request, task_id):
    """Mark task as completed"""
    user = _get_user_from_request(request)
    if not user:
        return _json_response({'error': 'Authentication required'}, status=401)
    
    if user.role != User.ROLE_CHILD:
        return _json_response({'error': 'Only children can complete tasks'}, status=403)
    
    family = get_family_for_user(user)
    if not family:
        return _json_response({'error': 'No family found'}, status=404)
    
    try:
        task = Task.objects.filter(family=family, id=task_id).first()
        if not task:
            return _json_response({'error': 'Task not found'}, status=404)
        
        if task.completed:
            return _json_response({'error': 'Task already completed'}, status=400)
        
        if not task.is_in_progress or task.assigned_to_id != user.id:
            return _json_response({'error': 'You can only complete tasks you started'}, status=403)
        
        task.completed = True
        task.completed_by = user
        task.completed_at = timezone.now()
        task.approved = False
        task.approved_by = None
        task.approved_at = None
        task.save()
        
        return _json_response({'message': 'Task completed successfully'})
    except Exception as e:
        return _json_response({'error': str(e)}, status=500)


@csrf_exempt
@require_http_methods(["POST"])
def approve_task(request, task_id):
    """Approve a completed task"""
    user = _get_user_from_request(request)
    if not user:
        return _json_response({'error': 'Authentication required'}, status=401)
    
    if user.role != User.ROLE_PARENT:
        return _json_response({'error': 'Only parents can approve tasks'}, status=403)
    
    family = get_family_for_user(user)
    if not family:
        return _json_response({'error': 'No family found'}, status=404)
    
    try:
        task = Task.objects.filter(family=family, id=task_id).first()
        if not task:
            return _json_response({'error': 'Task not found'}, status=404)
        
        if not task.completed:
            return _json_response({'error': 'Task is not completed'}, status=400)
        
        if task.approved:
            return _json_response({'error': 'Task already approved'}, status=400)
        
        assignee = task.assigned_to or task.completed_by
        if not assignee:
            return _json_response({'error': 'Task has no assignee'}, status=400)
        
        with transaction.atomic():
            task.approved = True
            task.approved_by = user
            task.approved_at = timezone.now()
            task.save()
            
            assignee.points += task.points
            assignee.save(update_fields=['points'])
            
            return _json_response({'message': 'Task approved successfully'})
    except Exception as e:
        return _json_response({'error': str(e)}, status=500)


@csrf_exempt
@require_http_methods(["POST"])
def unapprove_task(request, task_id):
    """Unapprove an approved task"""
    user = _get_user_from_request(request)
    if not user:
        return _json_response({'error': 'Authentication required'}, status=401)
    
    if user.role != User.ROLE_PARENT:
        return _json_response({'error': 'Only parents can unapprove tasks'}, status=403)
    
    family = get_family_for_user(user)
    if not family:
        return _json_response({'error': 'No family found'}, status=404)
    
    try:
        task = Task.objects.filter(family=family, id=task_id).first()
        if not task:
            return _json_response({'error': 'Task not found'}, status=404)
        
        if not task.approved:
            return _json_response({'error': 'Task is not approved'}, status=400)
        
        assignee = task.assigned_to or task.completed_by
        if not assignee:
            return _json_response({'error': 'Task has no assignee'}, status=400)
        
        with transaction.atomic():
            # Remove points from assignee
            assignee.points = max(0, assignee.points - task.points)
            assignee.save(update_fields=['points'])
            
            task.approved = False
            task.approved_by = None
            task.approved_at = None
            task.save()
            
            return _json_response({'message': 'Task unapproved successfully'})
    except Exception as e:
        return _json_response({'error': str(e)}, status=500)


@csrf_exempt
@require_http_methods(["DELETE"])
def delete_task(request, task_id):
    """Delete a task"""
    user = _get_user_from_request(request)
    if not user:
        return _json_response({'error': 'Authentication required'}, status=401)
    
    if user.role != User.ROLE_PARENT:
        return _json_response({'error': 'Only parents can delete tasks'}, status=403)
    
    family = get_family_for_user(user)
    if not family:
        return _json_response({'error': 'No family found'}, status=404)
    
    try:
        task = Task.objects.filter(family=family, id=task_id).first()
        if not task:
            return _json_response({'error': 'Task not found'}, status=404)
        
        task.delete()
        return _json_response({'message': 'Task deleted successfully'})
    except Exception as e:
        return _json_response({'error': str(e)}, status=500)


@require_http_methods(["GET"])
def get_rewards(request):
    """Get rewards for user's family"""
    user = _get_user_from_request(request)
    if not user:
        return _json_response({'error': 'Authentication required'}, status=401)
    
    family = get_family_for_user(user)
    if not family:
        return _json_response({'error': 'No family found'}, status=404)
    
    rewards = Reward.objects.filter(family=family).select_related(
        'created_by', 'claimed_by'
    ).order_by('claimed', '-created_at', 'name')
    
    rewards_data = []
    for reward in rewards:
        rewards_data.append({
            'id': reward.id,
            'name': reward.name,
            'description': reward.description,
            'points': reward.points,
            'created_by': {
                'id': reward.created_by.id,
                'display_name': reward.created_by.get_display_name(),
            },
            'claimed': reward.claimed,
            'claimed_by': {
                'id': reward.claimed_by.id,
                'display_name': reward.claimed_by.get_display_name(),
            } if reward.claimed_by else None,
            'claimed_at': reward.claimed_at.isoformat() if reward.claimed_at else None,
            'created_at': reward.created_at.isoformat(),
            'updated_at': reward.updated_at.isoformat(),
        })
    
    return _json_response(rewards_data)


@csrf_exempt
@require_http_methods(["POST"])
def create_reward(request):
    """Create a new reward"""
    user = _get_user_from_request(request)
    if not user:
        return _json_response({'error': 'Authentication required'}, status=401)
    
    if user.role != User.ROLE_PARENT:
        return _json_response({'error': 'Only parents can create rewards'}, status=403)
    
    family = get_family_for_user(user)
    if not family:
        return _json_response({'error': 'No family found'}, status=404)
    
    try:
        data = json.loads(request.body)
        name = data.get('name', '').strip()
        description = data.get('description', '').strip()
        points = int(data.get('points', 0))
        
        if not name:
            return _json_response({'error': 'Reward name required'}, status=400)
        
        # Check subscription limit
        can_create, current_count, limit, tier = check_subscription_limit(family, 'rewards', 1)
        if not can_create:
            return _json_response({
                'error': f'Reward limit reached ({current_count}/{limit})',
                'limit_reached': True,
            }, status=403)
        
        with transaction.atomic():
            reward = Reward.objects.create(
                name=name,
                description=description,
                points=points,
                family=family,
                created_by=user,
            )
            
            increment_usage(family, 'rewards', 1)
            
            return _json_response({
                'id': reward.id,
                'name': reward.name,
                'description': reward.description,
                'points': reward.points,
                'created_by': {
                    'id': reward.created_by.id,
                    'display_name': reward.created_by.get_display_name(),
                },
                'claimed': reward.claimed,
                'created_at': reward.created_at.isoformat(),
            }, status=201)
    except json.JSONDecodeError:
        return _json_response({'error': 'Invalid JSON'}, status=400)
    except Exception as e:
        return _json_response({'error': str(e)}, status=500)


@csrf_exempt
@require_http_methods(["POST"])
def claim_reward(request, reward_id):
    """Claim a reward"""
    user = _get_user_from_request(request)
    if not user:
        return _json_response({'error': 'Authentication required'}, status=401)
    
    family = get_family_for_user(user)
    if not family:
        return _json_response({'error': 'No family found'}, status=404)
    
    try:
        reward = Reward.objects.filter(family=family, id=reward_id).first()
        if not reward:
            return _json_response({'error': 'Reward not found'}, status=404)
        
        if reward.claimed:
            return _json_response({'error': 'Reward already claimed'}, status=400)
        
        if user.points < reward.points:
            return _json_response({'error': 'Insufficient points'}, status=400)
        
        with transaction.atomic():
            reward.claimed = True
            reward.claimed_by = user
            reward.claimed_at = timezone.now()
            reward.save()
            
            user.points -= reward.points
            user.save(update_fields=['points'])
            
            return _json_response({'message': 'Reward claimed successfully'})
    except Exception as e:
        return _json_response({'error': str(e)}, status=500)


@require_http_methods(["GET"])
def get_family(request):
    """Get user's family"""
    user = _get_user_from_request(request)
    if not user:
        return _json_response({'error': 'Authentication required'}, status=401)
    
    family = get_family_for_user(user)
    if not family:
        return _json_response({'error': 'No family found'}, status=404)
    
    members = list(family.members.all())
    if family.owner not in members:
        members.append(family.owner)
    
    members_data = []
    for member in members:
        members_data.append({
            'id': member.id,
            'username': member.username,
            'email': member.email,
            'first_name': member.first_name,
            'last_name': member.last_name,
            'role': member.role,
            'points': member.points,
            'display_name': member.get_display_name(),
        })
    
    return _json_response({
        'id': str(family.id),
        'name': family.name,
        'join_code': family.join_code,
        'owner': {
            'id': family.owner.id,
            'username': family.owner.username,
            'email': family.owner.email,
            'first_name': family.owner.first_name,
            'last_name': family.owner.last_name,
            'role': family.owner.role,
            'points': family.owner.points,
            'display_name': family.owner.get_display_name(),
        },
        'members': members_data,
        'created_at': family.created_at.isoformat(),
    })


@csrf_exempt
@require_http_methods(["POST"])
def join_family(request):
    """Join a family using join code"""
    user = _get_user_from_request(request)
    if not user:
        return _json_response({'error': 'Authentication required'}, status=401)
    
    try:
        data = json.loads(request.body)
        join_code = data.get('join_code', '').strip().upper()
        
        if not join_code:
            return _json_response({'error': 'Join code required'}, status=400)
        
        family = Family.objects.get(join_code=join_code)
        
        if family.owner == user or user in family.members.all():
            return _json_response({'error': 'Already a member of this family'}, status=400)
        
        can_add, current_count, limit, tier = family.can_add_member(user.role)
        if not can_add:
            return _json_response({
                'error': f'Family {user.get_role_display()}-limit reached ({current_count}/{limit})',
            }, status=403)
        
        with transaction.atomic():
            family.members.add(user)
            
            members = list(family.members.all())
            if family.owner not in members:
                members.append(family.owner)
            
            members_data = []
            for member in members:
                members_data.append({
                    'id': member.id,
                    'username': member.username,
                    'email': member.email,
                    'first_name': member.first_name,
                    'last_name': member.last_name,
                    'role': member.role,
                    'points': member.points,
                    'display_name': member.get_display_name(),
                })
            
            return _json_response({
                'id': str(family.id),
                'name': family.name,
                'join_code': family.join_code,
                'owner': {
                    'id': family.owner.id,
                    'username': family.owner.username,
                    'email': family.owner.email,
                    'first_name': family.owner.first_name,
                    'last_name': family.owner.last_name,
                    'role': family.owner.role,
                    'points': family.owner.points,
                    'display_name': family.owner.get_display_name(),
                },
                'members': members_data,
                'created_at': family.created_at.isoformat(),
            })
    except Family.DoesNotExist:
        return _json_response({'error': 'Invalid join code'}, status=404)
    except json.JSONDecodeError:
        return _json_response({'error': 'Invalid JSON'}, status=400)
    except Exception as e:
        return _json_response({'error': str(e)}, status=500)


@require_http_methods(["GET"])
def get_dashboard(request):
    """Get dashboard summary data"""
    user = _get_user_from_request(request)
    if not user:
        return _json_response({'error': 'Authentication required'}, status=401)
    
    family = get_family_for_user(user)
    if not family:
        return _json_response({'error': 'No family found'}, status=404)
    
    active_tasks = Task.objects.filter(family=family, completed=False).count()
    pending_tasks = Task.objects.filter(family=family, completed=True, approved=False).count()
    completed_tasks = Task.objects.filter(family=family, approved=True).count()
    
    available_rewards = Reward.objects.filter(family=family, claimed=False).count()
    claimed_rewards = Reward.objects.filter(family=family, claimed=True).count()
    
    return _json_response({
        'user': {
            'id': user.id,
            'display_name': user.get_display_name(),
            'points': user.points,
            'role': user.role,
        },
        'family': {
            'id': str(family.id),
            'name': family.name,
        },
        'tasks': {
            'active': active_tasks,
            'pending': pending_tasks,
            'completed': completed_tasks,
        },
        'rewards': {
            'available': available_rewards,
            'claimed': claimed_rewards,
        },
    })


@require_http_methods(["GET"])
def get_shopping_list(request):
    """Get shopping list items"""
    user = _get_user_from_request(request)
    if not user:
        return _json_response({'error': 'Authentication required'}, status=401)
    
    family = get_family_for_user(user)
    if not family:
        return _json_response({'error': 'No family found'}, status=404)
    
    if not has_shopping_list_access(family):
        return _json_response({'error': 'Shopping list access requires STARTER or PRO subscription'}, status=403)
    
    items = ShoppingListItem.objects.filter(family=family).select_related('added_by').order_by('in_cart', '-created_at', 'name')
    
    items_data = []
    for item in items:
        items_data.append({
            'id': item.id,
            'name': item.name,
            'in_cart': item.in_cart,
            'added_by': {
                'id': item.added_by.id,
                'display_name': item.added_by.get_display_name(),
            },
            'created_at': item.created_at.isoformat(),
            'updated_at': item.updated_at.isoformat(),
        })
    
    return _json_response(items_data)


@csrf_exempt
@require_http_methods(["POST"])
def create_shopping_item(request):
    """Create a shopping list item"""
    user = _get_user_from_request(request)
    if not user:
        return _json_response({'error': 'Authentication required'}, status=401)
    
    family = get_family_for_user(user)
    if not family:
        return _json_response({'error': 'No family found'}, status=404)
    
    if not has_shopping_list_access(family):
        return _json_response({'error': 'Shopping list access requires STARTER or PRO subscription'}, status=403)
    
    try:
        data = json.loads(request.body)
        name = data.get('name', '').strip()
        
        if not name:
            return _json_response({'error': 'Item name required'}, status=400)
        
        item = ShoppingListItem.objects.create(
            name=name,
            family=family,
            added_by=user,
        )
        
        return _json_response({
            'id': item.id,
            'name': item.name,
            'in_cart': item.in_cart,
            'added_by': {
                'id': item.added_by.id,
                'display_name': item.added_by.get_display_name(),
            },
            'created_at': item.created_at.isoformat(),
        }, status=201)
    except json.JSONDecodeError:
        return _json_response({'error': 'Invalid JSON'}, status=400)
    except Exception as e:
        return _json_response({'error': str(e)}, status=500)


@csrf_exempt
@require_http_methods(["PUT"])
def update_shopping_item(request, item_id):
    """Update a shopping list item"""
    user = _get_user_from_request(request)
    if not user:
        return _json_response({'error': 'Authentication required'}, status=401)
    
    family = get_family_for_user(user)
    if not family:
        return _json_response({'error': 'No family found'}, status=404)
    
    if not has_shopping_list_access(family):
        return _json_response({'error': 'Shopping list access requires STARTER or PRO subscription'}, status=403)
    
    try:
        item = ShoppingListItem.objects.filter(family=family, id=item_id).first()
        if not item:
            return _json_response({'error': 'Item not found'}, status=404)
        
        data = json.loads(request.body)
        
        if 'name' in data:
            item.name = data['name'].strip()
        if 'in_cart' in data:
            item.in_cart = bool(data['in_cart'])
        
        item.save()
        
        return _json_response({
            'id': item.id,
            'name': item.name,
            'in_cart': item.in_cart,
        })
    except json.JSONDecodeError:
        return _json_response({'error': 'Invalid JSON'}, status=400)
    except Exception as e:
        return _json_response({'error': str(e)}, status=500)


@csrf_exempt
@require_http_methods(["DELETE"])
def delete_shopping_item(request, item_id):
    """Delete a shopping list item"""
    user = _get_user_from_request(request)
    if not user:
        return _json_response({'error': 'Authentication required'}, status=401)
    
    family = get_family_for_user(user)
    if not family:
        return _json_response({'error': 'No family found'}, status=404)
    
    if not has_shopping_list_access(family):
        return _json_response({'error': 'Shopping list access requires STARTER or PRO subscription'}, status=403)
    
    try:
        item = ShoppingListItem.objects.filter(family=family, id=item_id).first()
        if not item:
            return _json_response({'error': 'Item not found'}, status=404)
        
        item.delete()
        return _json_response({'message': 'Item deleted successfully'})
    except Exception as e:
        return _json_response({'error': str(e)}, status=500)

