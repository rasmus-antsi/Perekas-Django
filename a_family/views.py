import logging

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from allauth.account.adapter import get_adapter

from .emails import send_family_created_email, send_family_member_joined_email
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
                    messages.error(request, f'Perega liitumisel tekkis viga: {str(e)}')
        
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
    
    context = {
        'family': family,
        'members': all_members,
        'is_owner': is_owner,
        'is_parent': is_parent,
    }
    return render(request, 'a_family/index.html', context)


@login_required
def remove_member(request, user_id):
    """Remove a member from the family - only owner can do this"""
    if request.method != 'POST':
        messages.error(request, 'Vale päringu meetod.')
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
            messages.success(request, f'{member_to_remove.get_full_name() or member_to_remove.username} eemaldati perest.')
        else:
            messages.info(request, 'See kasutaja ei kuulu sinu perre.')
    except User.DoesNotExist:
        messages.error(request, 'Kasutajat ei leitud.')
    
    return redirect('a_family:index')


def resend_verification_email(request):
    """Resend email verification email - works for both authenticated and unauthenticated users"""
    if request.method == 'POST':
        email = request.POST.get('email')
        if not email:
            messages.error(request, 'Palun sisesta e-posti aadress.')
            return redirect('account_email_verification_sent')
        
        try:
            from allauth.account.models import EmailAddress
            email_address = EmailAddress.objects.get(email=email)
            if email_address.verified:
                messages.info(request, 'See e-posti aadress on juba kinnitatud.')
                return redirect('account_email_verification_sent')
            
            # Resend verification email using our async adapter
            adapter = get_adapter(request)
            adapter.send_confirmation_mail(request, email_address, signup=False)
            messages.success(request, 'Kinnituse kiri saadeti uuesti. Palun kontrolli oma e-posti.')
        except EmailAddress.DoesNotExist:
            messages.error(request, 'See e-posti aadress ei ole meie süsteemis.')
        except Exception as e:
            logger = logging.getLogger(__name__)
            logger.error(f"Failed to resend verification email: {str(e)}", exc_info=True)
            messages.error(request, 'E-kirja saatmisel tekkis viga. Palun proovi hiljem uuesti.')
    
    return redirect('account_email_verification_sent')
