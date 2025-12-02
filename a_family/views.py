# Standard library imports
import logging

# Django imports
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render

# Third-party imports
from allauth.account.adapter import get_adapter
from allauth.account.models import EmailAddress

# Local application imports
from .emails import send_family_created_email, send_family_member_joined_email, send_admin_family_created_notification
from .forms import CreateFamilyForm, JoinFamilyForm
from .models import Family, User
from .utils import get_family_for_user as _get_family_for_user


@login_required
def onboarding(request):
    """Family onboarding page - create or join a family"""
    user = request.user
    
    # Check email verification - block access until verified
    if user.email:
        try:
            email_address = EmailAddress.objects.filter(
                user=user,
                email=user.email,
                primary=True
            ).first()
            
            if email_address and not email_address.verified:
                # Email not verified - redirect to verification page
                messages.error(
                    request,
                    'Perekonna loomiseks või liitumiseks peab e-posti aadress olema kinnitatud. '
                    'Palun kinnita oma e-post ja proovi uuesti.'
                )
                return redirect('account_verification_sent')
        except Exception:
            # If there's an error checking, allow access
            pass
    
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
                try:
                    family = Family.objects.create(
                        name=family_name,
                        owner=user,
                    )
                    family.members.add(user)
                    messages.success(request, f'Pere "{family_name}" loodud edukalt!')
                except Exception as e:
                    import logging
                    logger = logging.getLogger(__name__)
                    logger.error(f"Error creating family: {e}", exc_info=True)
                    from django.conf import settings
                    messages.error(request, f"Midagi läks valesti pere loomisel. Kui probleem püsib, palun võta ühendust tugiteenusega: {settings.SUPPORT_EMAIL}")
                    return redirect('a_family:onboarding')
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
                    from django.conf import settings
                    messages.error(request, f"Midagi läks valesti. Kui probleem püsib, palun võta ühendust tugiteenusega: {settings.SUPPORT_EMAIL}")
        
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
        'user_last_name': user.last_name or '',
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
    
    is_parent = user.role == User.ROLE_PARENT
    is_owner = family.owner == user
    
    from django.utils import timezone
    from datetime import date
    
    context = {
        'family': family,
        'join_code': family.join_code,
        'members': family.members.all(),
        'owner': family.owner,
        'is_parent': is_parent,
        'is_owner': is_owner,
        'today': date.today(),
    }
    return render(request, 'a_family/index.html', context)


@login_required
def remove_member(request, user_id):
    """Remove a member from the family"""
    user = request.user
    family = _get_family_for_user(user)
    
    # Check if user is the owner
    if not family or family.owner != user:
        messages.error(request, 'Ainult pere omanik saab liikmeid eemaldada.')
        return redirect('a_family:index')
    
    # Get the member to remove
    try:
        member_to_remove = User.objects.get(id=user_id)
    except User.DoesNotExist:
        messages.error(request, 'Liiget ei leitud.')
        return redirect('a_family:index')
    
    # Can't remove yourself or the owner
    if member_to_remove == user:
        messages.error(request, 'Sa ei saa end eemaldada.')
        return redirect('a_family:index')
    
    # Remove the member
    family.members.remove(member_to_remove)
    messages.success(request, f'{member_to_remove.get_display_name()} eemaldati perest.')
    
    return redirect('a_family:index')


@login_required
def verification_sent(request):
    """
    Custom view for email verification sent page.
    Allows users to resend verification email or change their email address.
    """
    user = request.user
    
    # Get current email
    current_email = user.email if user.email else ''
    
    # Get email address record
    email_address = None
    if current_email:
        try:
            email_address = EmailAddress.objects.filter(
                user=user,
                email=current_email,
                primary=True
            ).first()
        except Exception:
            pass
    
    context = {
        'email': current_email,
        'email_verified': email_address.verified if email_address else False,
        'user': user,
    }
    
    return render(request, 'account/verification_sent.html', context)


def resend_verification_email(request):
    """Resend email verification email or change email - works for both authenticated and unauthenticated users"""
    logger = logging.getLogger(__name__)
    
    if request.method == 'POST':
        action = request.POST.get('action', 'resend')
        email = request.POST.get('email', '').strip()
        new_email = request.POST.get('new_email', '').strip()
        
        # Handle email change
        if action == 'change_email' and new_email:
            if not request.user.is_authenticated:
                messages.error(request, 'E-posti muutmiseks pead olema sisse logitud.')
                return redirect('account_login')
            
            user = request.user
            
            # Validate new email
            if not new_email:
                messages.error(request, 'Palun sisesta uus e-posti aadress.')
                return redirect('account_verification_sent')
            
            # Check if email is already in use
            if User.objects.filter(email=new_email).exclude(id=user.id).exists():
                messages.error(request, 'See e-posti aadress on juba kasutusel.')
                return redirect('account_verification_sent')
            
            # Update user email
            user.email = new_email
            user.save()
            
            # Delete old email address records
            EmailAddress.objects.filter(user=user).delete()
            
            # Create new EmailAddress record
            email_address = EmailAddress.objects.create(
                email=new_email,
                user=user,
                primary=True,
                verified=False
            )
            
            # Use allauth's send_confirmation method which handles both HMAC and database confirmations
            # send_confirmation() creates the confirmation AND sends the email internally
            # This ensures we use the same confirmation method as during signup
            email_address.send_confirmation(request, signup=False)
            
            messages.success(
                request,
                f'E-posti aadress muudetud. Saatsime kinnituse kirja aadressile {new_email}. '
                'Palun kontrolli oma e-posti ja klõpsa kinnituse lingil.'
            )
            return redirect('account_verification_sent')
        
        # Handle resend verification
        if not email:
            email = request.user.email if request.user.is_authenticated else ''
        
        if not email:
            messages.error(request, 'Palun sisesta e-posti aadress.')
            return redirect('account_verification_sent')
        
        try:
            from allauth.account.adapter import DefaultAccountAdapter
            
            email_address = EmailAddress.objects.get(email=email)
            if email_address.verified:
                messages.info(request, 'See e-posti aadress on juba kinnitatud.')
                if request.user.is_authenticated:
                    return redirect('a_dashboard:dashboard')
                return redirect('account_login')
            
            # Resend verification email - use allauth's method which handles HMAC vs database confirmations
            # send_confirmation() creates the confirmation AND sends the email internally
            # This ensures we use the same confirmation method as during signup
            email_address.send_confirmation(request, signup=False)
            
            logger.info(f"Email verification resent synchronously to {email} for user {email_address.user_id}")
            messages.success(request, 'Kinnituse kiri saadeti uuesti. Palun kontrolli oma e-posti.')
            
            return redirect('account_verification_sent')
        except EmailAddress.DoesNotExist:
            from django.conf import settings
            messages.error(request, f"Midagi läks valesti. Kui probleem püsib, palun võta ühendust tugiteenusega: {settings.SUPPORT_EMAIL}")
            return redirect('account_verification_sent')
        except Exception as e:
            logger.error(f"Failed to resend verification email: {str(e)}", exc_info=True)
            from django.conf import settings
            messages.error(request, f"Midagi läks valesti. Kui probleem püsib, palun võta ühendust tugiteenusega: {settings.SUPPORT_EMAIL}")
            return redirect('account_verification_sent')
    
    # GET request - show verification sent page
    return redirect('account_verification_sent')


@login_required
def delete_family(request):
    """Delete family - only for family owner"""
    from django.urls import reverse
    user = request.user
    
    if request.method != 'POST':
        messages.error(request, "Midagi läks valesti.")
        return redirect(f"{reverse('a_account:settings')}?section=general")
    
    # Get the family
    family = _get_family_for_user(user)
    if not family:
        messages.error(request, 'Sa ei kuulu ühelegi peresse.')
        return redirect(f"{reverse('a_account:settings')}?section=general")
    
    # Check if user is the family owner
    if family.owner != user:
        messages.error(request, 'Ainult pere omanik saab pere kustutada.')
        return redirect(f"{reverse('a_account:settings')}?section=general")
    
    family_name = family.name
    
    delete_children_choice = request.POST.get('delete_children', 'delete')
    if delete_children_choice not in ('delete', 'keep'):
        delete_children_choice = 'delete'

    child_accounts = list(family.members.filter(role=User.ROLE_CHILD))
    if delete_children_choice == 'delete':
        for child in child_accounts:
            try:
                from allauth.account.models import EmailAddress
                EmailAddress.objects.filter(user=child).delete()
            except Exception:
                pass
            child.delete()
    else:
        for child in child_accounts:
            family.members.remove(child)

    # Remove remaining members from the family to break associations
    family.members.clear()
    
    # Note: Tasks have CASCADE delete on family FK (family=models.ForeignKey(Family, on_delete=models.CASCADE))
    # So they'll be deleted automatically when the family is deleted
    # Shopping items, rewards, etc. are tied to users, not families, so they stay
    
    # Delete the family (this will CASCADE delete tasks)
    family.delete()
    
    messages.success(request, f'Pere "{family_name}" kustutatud edukalt.')
    return redirect('a_dashboard:dashboard')


@login_required
def delete_child_account(request):
    """Delete child account - only for parents"""
    user = request.user
    
    # Check if user is a parent
    if user.role != User.ROLE_PARENT:
        messages.error(request, 'Ainult lapsevanemad saavad laste kontosid kustutada.')
        return redirect('a_dashboard:dashboard')
    
    if request.method != 'POST':
        messages.error(request, "Midagi läks valesti.")
        return redirect('a_family:index')
    
    child_id = request.POST.get('child_id')
    if not child_id:
        messages.error(request, "Lapse ID puudub.")
        return redirect('a_family:index')
    
    try:
        child_id = int(child_id)
    except (ValueError, TypeError):
        messages.error(request, "Vale lapse ID.")
        return redirect('a_family:index')
    
    # Get the family
    family = _get_family_for_user(user)
    if not family:
        messages.error(request, 'Sa ei kuulu ühelegi peresse.')
        return redirect('a_family:onboarding')
    
    # Get the child
    try:
        child = User.objects.get(id=child_id, role=User.ROLE_CHILD)
    except User.DoesNotExist:
        messages.error(request, 'Last ei leitud.')
        return redirect('a_family:index')
    
    # Check if child is in the family
    if child not in family.members.all() and child != family.owner:
        messages.error(request, 'See laps ei kuulu sinu peresse.')
        return redirect('a_family:index')
    
    # Can't delete family owner
    if child == family.owner:
        messages.error(request, 'Pere omaniku kontot ei saa kustutada.')
        return redirect('a_family:index')
    
    child_name = child.get_display_name()
    
    # Remove child from family
    family.members.remove(child)
    
    # Delete EmailAddress records
    try:
        from allauth.account.models import EmailAddress
        EmailAddress.objects.filter(user=child).delete()
    except Exception:
        pass
    
    # Delete child account
    child.delete()
    
    messages.success(request, f'{child_name} konto kustutatud edukalt.')
    return redirect('a_family:index')


@login_required
def manage_child_account(request, child_id):
    """Parent view to manage child account - edit profile, reset password, manage email"""
    user = request.user
    
    # Check if user is a parent
    if user.role != User.ROLE_PARENT:
        messages.error(request, 'Ainult lapsevanemad saavad laste kontosid hallata.')
        return redirect('a_dashboard:dashboard')
    
    # Get the family
    family = _get_family_for_user(user)
    if not family:
        messages.error(request, 'Sa ei kuulu ühelegi peresse.')
        return redirect('a_family:onboarding')
    
    # Get the child
    try:
        child = User.objects.get(id=child_id, role=User.ROLE_CHILD)
    except User.DoesNotExist:
        messages.error(request, 'Last ei leitud.')
        return redirect('a_family:index')
    
    # Check if child is in the family
    if child not in family.members.all() and child != family.owner:
        messages.error(request, 'See laps ei kuulu sinu peresse.')
        return redirect('a_family:index')
    
    if request.method == 'POST':
        # Handle AJAX request for child data
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            from django.http import JsonResponse
            return JsonResponse({
                'id': child.id,
                'username': child.username,
                'first_name': child.first_name,
                'last_name': child.last_name,
                'email': child.email or '',
                'birthdate': child.birthdate.isoformat() if child.birthdate else '',
            })
        
        # Handle form submission
        username = request.POST.get('username', '').strip()
        first_name = request.POST.get('first_name', '').strip()
        last_name = request.POST.get('last_name', '').strip()
        email = request.POST.get('email', '').strip()
        password = request.POST.get('password', '').strip()
        
        updated_fields = set()
        
        # Update username
        if username and username != child.username:
            # Check if username is already in use
            if User.objects.filter(username=username).exclude(id=child.id).exists():
                messages.error(request, "See kasutajanimi on juba kasutusel.")
                return redirect('a_family:index')
            child.username = username
            updated_fields.add('username')
        
        # Update first name
        if first_name and first_name != child.first_name:
            child.first_name = first_name
            updated_fields.add('first_name')
        
        # Update last name
        if last_name and last_name != child.last_name:
            child.last_name = last_name
            updated_fields.add('last_name')
        
        # Update password
        if password:
            child.set_password(password)
            updated_fields.add('password')
        
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
                
                # Update EmailAddress records
                try:
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
                    EmailAddress.objects.filter(user=child).delete()
                except Exception:
                    pass
        
        # Save updates
        if updated_fields:
            try:
                logger = logging.getLogger(__name__)
                child.save(update_fields=list(updated_fields))
                messages.success(request, f'{child.get_display_name()} andmed uuendatud.')
            except Exception as e:
                logger = logging.getLogger(__name__)
                logger.error(f"Error updating child {child.id}: {str(e)}", exc_info=True)
                messages.error(request, "Midagi läks valesti andmete uuendamisel.")
        else:
            messages.info(request, 'Muudatusi ei tehtud.')
        
        return redirect('a_family:index')
    
    # GET request - return child data as JSON
    from django.http import JsonResponse
    return JsonResponse({
        'id': child.id,
        'username': child.username,
        'first_name': child.first_name,
        'last_name': child.last_name,
        'email': child.email or '',
        'birthdate': child.birthdate.isoformat() if child.birthdate else '',
    })
