import logging
import threading

from allauth.account.adapter import DefaultAccountAdapter
from allauth.account import app_settings


logger = logging.getLogger(__name__)


class AsyncAccountAdapter(DefaultAccountAdapter):
    """
    Account adapter that dispatches transactional emails on a background thread
    so that signup/login views respond immediately, even if SMTP is slow.
    Also handles children accounts that may not have email addresses.
    """

    def send_mail(self, template_prefix, email, context):
        """Send email - skip if email is None (for children without email)"""
        if not email:
            logger.info("Skipping email send for user without email")
            return
        
        # Ensure user object has display_name accessible in template
        if 'user' in context and context['user']:
            user = context['user']
            # Ensure display_name is available in context
            if not hasattr(user, 'display_name'):
                # If display_name property doesn't exist, add it as a method result
                try:
                    context['user_display_name'] = user.get_display_name()
                except Exception:
                    context['user_display_name'] = user.username or 'Perekas kasutaja'
        
        def _runner():
            try:
                super(AsyncAccountAdapter, self).send_mail(template_prefix, email, context)
            except Exception:
                logger.exception("Failed to send account email to %s", email)

        threading.Thread(target=_runner, daemon=True).start()
    
    def save_user(self, request, user, form, commit=True):
        """Override to handle children without email"""
        # Check if this is a child without email
        role = None
        has_email = None
        if hasattr(form, 'cleaned_data') and 'role' in form.cleaned_data:
            role = form.cleaned_data.get('role')
            has_email = form.data.get('has_email', '') if hasattr(form, 'data') else None
        elif hasattr(form, 'data'):
            role = form.data.get('role')
            has_email = form.data.get('has_email', '')
        
        is_child_without_email = (role == 'child' and has_email == 'no')
        
        # If child without email, remove email from cleaned_data BEFORE calling super
        if is_child_without_email and hasattr(form, 'cleaned_data'):
            if 'email' in form.cleaned_data:
                del form.cleaned_data['email']
        
        # Call parent save_user (which creates the user)
        user = super().save_user(request, user, form, commit=False)
        
        # If child without email, explicitly set email to None BEFORE saving
        if is_child_without_email:
            user.email = None
        
        # Save the user (with email=None for children without email)
        if commit:
            try:
                user.save()
            except Exception as e:
                # If we get an IntegrityError about email being NOT NULL, the migration hasn't been run
                if 'NOT NULL constraint failed: auth_user.email' in str(e) or 'email' in str(e).lower():
                    logger.error(
                        "Database migration not applied! The email field is still NOT NULL. "
                        "Please run: python manage.py migrate a_family"
                    )
                    raise Exception(
                        "Database schema is out of date. Please contact support or run migrations."
                    ) from e
                raise
        
        return user
    
    def is_email_verification_required(self, request):
        """Require email verification for parents, skip for children without email"""
        # Check if user is a child without email from the request
        if hasattr(request, 'user') and request.user.is_authenticated:
            if request.user.role == 'child' and not request.user.email:
                return False
            # For parents, require email verification
            if request.user.role == 'parent' and request.user.email:
                return True
        
        # Also check during signup - if form has role='child' and has_email='no'
        if request.method == 'POST':
            role = request.POST.get('role')
            has_email = request.POST.get('has_email')
            email = request.POST.get('email', '').strip()
            if role == 'child' and has_email == 'no':
                return False
            # For parents, require email verification if email is provided
            if role == 'parent' and email:
                return True
        
        # Default to optional (global setting)
        return super().is_email_verification_required(request)
    
    def get_email_verification_method(self, request, user):
        """Require email verification for parents, skip for children without email"""
        if hasattr(user, 'role'):
            if user.role == 'child' and not user.email:
                return app_settings.EmailVerificationMethod.NONE
            # For parents with email, require verification
            if user.role == 'parent' and user.email:
                return app_settings.EmailVerificationMethod.MANDATORY
        return super().get_email_verification_method(request, user)
    
    def is_open_for_signup(self, request):
        """Allow signup for all users, including children without email"""
        return True

