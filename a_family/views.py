import logging

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from allauth.account.adapter import get_adapter

from .emails import send_family_created_email, send_family_member_joined_email, send_admin_family_created_notification
from .forms import CreateFamilyForm, JoinFamilyForm
from .models import Family, User


def _get_family_for_user(user):
    """Get the first family for a user (as owner or member)"""
    try:
        # Try to get family where user is a member first (more common)
        family = Family.objects.filter(members=user).first()
        if family is None:
            # If not a member, check if user is owner
            family = Family.objects.filter(owner=user).first()
        return family
    except Exception as e:
        # Log error but don't crash - return None so user can still access onboarding
        logger = logging.getLogger(__name__)
        logger.error(f"Error getting family for user {user.id}: {str(e)}", exc_info=True)
        return None


@login_required
def onboarding(request):
    """Family onboarding page - create or join a family"""
    user = request.user
    
    try:
        # If user already has a family, redirect to dashboard
        family = _get_family_for_user(user)
        if family:
            return redirect('a_dashboard:dashboard')
    except Exception as e:
        # Log error but allow user to continue to onboarding page
        logger = logging.getLogger(__name__)
        logger.error(f"Error in onboarding view for user {user.id if user.is_authenticated else 'anonymous'}: {str(e)}", exc_info=True)
        # Continue to show onboarding page even if there's an error
    
    is_parent = user.role == User.ROLE_PARENT
    is_child = user.role == User.ROLE_CHILD
    
    create_form = CreateFamilyForm()
    join_form = JoinFamilyForm()
    error_message = None
    
    if request.method == 'POST':
        action = request.POST.get('action')
        
        if action == 'create' and is_parent:
            create_form = CreateFamilyForm(request.POST)
            if create_form.is_valid():
                family_name = create_form.cleaned_data['name']
                family = Family.objects.create(
                    name=family_name,
                    owner=user,
                )
                family.members.add(user)
                messages.success(request, f'Pere "{family_name}" loodud edukalt!')
                try:
                    send_family_created_email(request, user, family)
                except Exception as email_error:
                    logging.getLogger(__name__).warning(
                        "Unable to send family created email: %s", email_error, exc_info=True
                    )
                # Send admin notification about new family
                try:
                    send_admin_family_created_notification(request, family)
                except Exception as email_error:
                    logging.getLogger(__name__).warning(
                        "Unable to send admin family created notification: %s", email_error, exc_info=True
                    )
                return redirect('a_dashboard:dashboard')
        
        elif action == 'join':
            join_form = JoinFamilyForm(request.POST)
            if join_form.is_valid():
                join_code = join_form.cleaned_data['join_code']
                try:
                    from django.db import transaction
                    
                    with transaction.atomic():
                        # Use select_for_update to prevent race conditions
                        family = Family.objects.select_for_update().get(join_code=join_code)
                        
                        # Check if user is already a member
                        if family.owner == user or user in family.members.all():
                            messages.info(request, 'Sa oled selle pere liige juba.')
                            return redirect('a_dashboard:dashboard')
                        
                        # Check subscription limits (re-check after locking to prevent race conditions)
                        can_add, current_count, limit, tier = family.can_add_member(user.role)
                        if not can_add:
                            messages.error(
                                request,
                                f'Selle pere {user.get_role_display()}-limiit on täis ({current_count}/{limit}). '
                                f'Palun uuenda tellimust.'
                            )
                        else:
                            family.members.add(user)
                            messages.success(request, f'Liitusid perega "{family.name}"!')
                            try:
                                send_family_member_joined_email(request, family, user)
                            except Exception as email_error:
                                logging.getLogger(__name__).warning(
                                    "Unable to send member joined email: %s", email_error, exc_info=True
                                )
                            return redirect('a_dashboard:dashboard')
                except Family.DoesNotExist:
                    error_message = 'Vale peresissekood. Palun kontrolli ja proovi uuesti.'
                except Exception as e:
                    messages.error(request, "Midagi läks valesti. Kui probleem püsib, palun võta ühendust tugiteenusega: tugi@perekas.ee")
        
        else:
            if action == 'create' and not is_parent:
                messages.error(request, 'Ainult lapsevanemad saavad peret luua.')
            error_message = 'Palun paranda allolevad vead.'
    
    context = {
        'is_parent': is_parent,
        'is_child': is_child,
        'create_form': create_form,
        'join_form': join_form,
        'error_message': error_message,
    }
    return render(request, 'a_family/onboarding.html', context)


@login_required
def index(request):
    """Family page - shows family info and invite code"""
    user = request.user
    family = _get_family_for_user(user)
    
    # Redirect to onboarding if user doesn't have a family
    if not family:
        messages.info(request, "Perega liitumiseks või uue pere loomiseks palun täida pere andmed.")
        return redirect('a_family:onboarding')
    
    # Redirect children - they can't see the family page
    if user.role == User.ROLE_CHILD:
        messages.info(request, 'Pere haldamine on lubatud ainult lapsevanematele.')
        return redirect('a_dashboard:dashboard')
    
    # Get all family members
    all_members = [family.owner]
    all_members.extend(family.members.all())
    # Remove duplicates
    all_members = list(dict.fromkeys(all_members))
    
    is_owner = family.owner == user
    is_parent = user.role == User.ROLE_PARENT
    
    from datetime import date
    
    context = {
        'family': family,
        'members': all_members,
        'is_owner': is_owner,
        'is_parent': is_parent,
        'today': date.today(),
    }
    return render(request, 'a_family/index.html', context)


@login_required
def remove_member(request, user_id):
    """Remove a member from the family - only owner can do this"""
    if request.method != 'POST':
        messages.error(request, "Midagi läks valesti. Kui probleem püsib, palun võta ühendust tugiteenusega: tugi@perekas.ee")
        return redirect('a_family:index')
    
    user = request.user
    family = _get_family_for_user(user)
    
    # Redirect if no family
    if not family:
        return redirect('a_family:onboarding')
    
    # Only owner can remove members
    if family.owner != user:
        messages.error(request, 'Ainult pere omanik saab liikmeid eemaldada.')
        return redirect('a_family:index')
    
    try:
        member_to_remove = User.objects.get(id=user_id)
        
        # Can't remove the owner
        if member_to_remove == family.owner:
            messages.error(request, 'Pere omanikku ei saa eemaldada.')
            return redirect('a_family:index')
        
        # Remove from members
        if member_to_remove in family.members.all():
            family.members.remove(member_to_remove)
            messages.success(request, f'{member_to_remove.get_display_name()} eemaldati perest.')
        else:
            messages.info(request, 'See kasutaja ei kuulu sinu perre.')
    except User.DoesNotExist:
        messages.error(request, "Midagi läks valesti. Kui probleem püsib, palun võta ühendust tugiteenusega: tugi@perekas.ee")
    
    return redirect('a_family:index')


def resend_verification_email(request):
    """Resend email verification email - works for both authenticated and unauthenticated users"""
    logger = logging.getLogger(__name__)
    
    if request.method == 'POST':
        email = request.POST.get('email')
        if not email:
            messages.error(request, 'Palun sisesta e-posti aadress.')
            # Always redirect to settings for authenticated users
            if request.user.is_authenticated:
                return redirect('a_account:settings')
            # For unauthenticated users, redirect back to verification sent page with email
            from django.shortcuts import render
            return render(request, 'account/verification_sent.html', {'email': ''})
        
        try:
            from allauth.account.models import EmailAddress
            from allauth.account.adapter import DefaultAccountAdapter
            from django.shortcuts import redirect
            
            email_address = EmailAddress.objects.get(email=email)
            if email_address.verified:
                messages.info(request, 'See e-posti aadress on juba kinnitatud.')
                # Always redirect to settings for authenticated users
                if request.user.is_authenticated:
                    return redirect('a_account:settings')
                # For unauthenticated users, redirect back to verification sent page
                from django.shortcuts import render
                return render(request, 'account/verification_sent.html', {'email': email})
            
            # Resend verification email synchronously
            # Manually create confirmation and send email to bypass async adapter
            from allauth.account.models import EmailConfirmation
            from allauth.account.adapter import DefaultAccountAdapter
            from django.utils import timezone
            
            sync_adapter = DefaultAccountAdapter()
            
            # Delete ALL existing confirmations for this email address to ensure only one valid link
            # This prevents confusion from multiple valid confirmation links
            EmailConfirmation.objects.filter(email_address=email_address).delete()
            
            # Create new email confirmation - create() returns and saves the object
            confirmation = EmailConfirmation.create(email_address)
            confirmation.sent = timezone.now()
            confirmation.save()
            
            # Refresh from database to ensure it's properly saved
            confirmation.refresh_from_db()
            
            # Build context
            activate_url = sync_adapter.get_email_confirmation_url(request, confirmation)
            ctx = {
                "user": email_address.user,
                "activate_url": activate_url,
                "key": confirmation.key,
                "request": request,
            }
            
            # Ensure user display name is in context
            if 'user' in ctx and ctx['user']:
                if not hasattr(ctx['user'], 'display_name'):
                    try:
                        ctx['user_display_name'] = ctx['user'].get_display_name()
                    except Exception:
                        ctx['user_display_name'] = ctx['user'].username or 'Perekas kasutaja'
            
            # Send email synchronously using parent's send_mail method
            # This bypasses our async adapter
            template_prefix = "account/email/email_confirmation"
            DefaultAccountAdapter.send_mail(sync_adapter, template_prefix, email, ctx)
            
            logger.info(f"Email verification resent synchronously to {email} for user {email_address.user_id}")
            messages.success(request, 'Kinnituse kiri saadeti uuesti. Palun kontrolli oma e-posti.')
            
            # Always redirect to settings for authenticated users
            if request.user.is_authenticated:
                return redirect('a_account:settings')
            # For unauthenticated users, render the verification sent page with email
            from django.shortcuts import render
            return render(request, 'account/verification_sent.html', {'email': email})
        except EmailAddress.DoesNotExist:
            messages.error(request, "Midagi läks valesti. Kui probleem püsib, palun võta ühendust tugiteenusega: tugi@perekas.ee")
            if request.user.is_authenticated:
                return redirect('a_account:settings')
            from django.shortcuts import render
            return render(request, 'account/verification_sent.html', {'email': email or ''})
        except Exception as e:
            logger.error(f"Failed to resend verification email: {str(e)}", exc_info=True)
            messages.error(request, "Midagi läks valesti. Kui probleem püsib, palun võta ühendust tugiteenusega: tugi@perekas.ee")
            if request.user.is_authenticated:
                return redirect('a_account:settings')
            from django.shortcuts import render
            return render(request, 'account/verification_sent.html', {'email': email or ''})
    
    # GET request - redirect to settings for authenticated users
    if request.user.is_authenticated:
        return redirect('a_account:settings')
    from django.shortcuts import render
    return render(request, 'account/verification_sent.html', {'email': ''})


@login_required
def manage_child_account(request, child_id):
    """Manage child account - only parents can do this"""
    parent = request.user
    family = _get_family_for_user(parent)
    
    # Only parents can manage child accounts
    if parent.role != User.ROLE_PARENT:
        messages.error(request, 'Ainult lapsevanemad saavad laste kontosid hallata.')
        return redirect('a_family:index')
    
    # Must be family owner or member
    if not family:
        messages.error(request, 'Pere puudub.')
        return redirect('a_family:onboarding')
    
    # Must be family owner to manage child accounts
    if family.owner != parent:
        messages.error(request, 'Ainult pere omanik saab laste kontosid hallata.')
        return redirect('a_family:index')
    
    try:
        child = User.objects.get(id=child_id)
    except User.DoesNotExist:
        messages.error(request, 'Lapse konto ei leitud.')
        return redirect('a_family:index')
    
    # Verify child belongs to this family
    if child != family.owner and child not in family.members.all():
        messages.error(request, 'See laps ei kuulu sinu perre.')
        return redirect('a_family:index')
    
    # Verify child is actually a child
    if child.role != User.ROLE_CHILD:
        messages.error(request, 'Seda funktsiooni saab kasutada ainult laste kontode jaoks.')
        return redirect('a_family:index')
    
    # Return JSON for modal load
    if request.GET.get('format') == 'json':
        from django.http import JsonResponse
        return JsonResponse({
            'id': child.id,
            'username': child.username,
            'first_name': child.first_name or '',
            'last_name': child.last_name or '',
            'birthdate': child.birthdate.strftime('%Y-%m-%d') if child.birthdate else '',
            'email': child.email or '',
        })
    
    # Handle form submission
    if request.method == 'POST' and request.POST.get('form_type') == 'child_account':
        from datetime import datetime
        
        username = request.POST.get('username', '').strip()
        first_name = request.POST.get('first_name', '').strip()
        last_name = request.POST.get('last_name', '').strip()
        birthdate_str = request.POST.get('birthdate', '').strip()
        email = request.POST.get('email', '').strip()
        new_password = request.POST.get('new_password', '').strip()
        
        updated_fields = set()
        
        # Update username (with uniqueness check)
        if username and username != child.username:
            if User.objects.filter(username=username).exclude(id=child.id).exists():
                messages.error(request, "See kasutajanimi on juba kasutusel.")
                return redirect('a_family:index')
            child.username = username
            updated_fields.add('username')
        
        # Update first and last name
        if first_name != child.first_name:
            child.first_name = first_name
            updated_fields.add('first_name')
        
        if last_name != child.last_name:
            child.last_name = last_name
            updated_fields.add('last_name')
        
        # Update birthdate
        if birthdate_str:
            try:
                birthdate = datetime.strptime(birthdate_str, '%Y-%m-%d').date()
                if child.birthdate != birthdate:
                    child.birthdate = birthdate
                    updated_fields.add('birthdate')
            except ValueError:
                messages.error(request, "Vale sünniaja vorming.")
                return redirect('a_family:index')
        elif child.birthdate:
            child.birthdate = None
            updated_fields.add('birthdate')
        
        # Update email
        if email != (child.email or ''):
            if email:
                # Check if email is already in use
                if User.objects.filter(email=email).exclude(id=child.id).exists():
                    messages.error(request, "See e-posti aadress on juba kasutusel.")
                    return redirect('a_family:index')
                
                # Update email
                child.email = email
                updated_fields.add('email')
                
                # Create/update EmailAddress records (not verified)
                try:
                    from allauth.account.models import EmailAddress
                    # Remove old email addresses
                    EmailAddress.objects.filter(user=child).exclude(email=email).delete()
                    # Create or update EmailAddress
                    email_address, created = EmailAddress.objects.get_or_create(
                        email=email,
                        user=child,
                        defaults={'primary': True, 'verified': False}
                    )
                    if not created:
                        email_address.primary = True
                        email_address.verified = False
                        email_address.save()
                except Exception:
                    pass
            else:
                # Email removed - parent cleared the email field
                child.email = None
                updated_fields.add('email')
                # Remove email address records
                try:
                    from allauth.account.models import EmailAddress
                    EmailAddress.objects.filter(user=child).delete()
                except Exception:
                    pass
        
        # Update password (if provided - no old password required for parents)
        if new_password:
            # Validate password using Django's password validators
            from django.contrib.auth.password_validation import validate_password
            from django.core.exceptions import ValidationError
            
            try:
                validate_password(new_password, user=child)
                child.set_password(new_password)
                updated_fields.add('password')
                messages.success(request, "Parool muudetud edukalt!")
            except ValidationError as e:
                error_messages = e.messages
                messages.error(request, f"Parooli valideerimine ebaõnnestus: {', '.join(error_messages)}")
                return redirect('a_family:index')
        
        # Save updates
        if updated_fields:
            child.save(update_fields=list(updated_fields))
            messages.success(request, f"Lapse '{child.get_display_name()}' andmed uuendatud.")
        
        return redirect('a_family:index')
    
    # Default redirect
    return redirect('a_family:index')
