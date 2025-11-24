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
        """Send email - skip if email is None (for children without email)
        Send confirmation emails synchronously, others asynchronously.
        """
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
        
        # Send confirmation emails synchronously to ensure confirmation is properly saved
        # before the email is sent (critical for verification links to work)
        # Check for both template prefix patterns that allauth uses
        is_confirmation_email = (
            'email_confirmation' in template_prefix or 
            'email/email_confirmation' in template_prefix or
            template_prefix == 'account/email/email_confirmation' or
            '/email_confirmation' in template_prefix
        )
        if is_confirmation_email:
            try:
                # Log for debugging
                logger.info(f"Sending confirmation email synchronously to {email}, template: {template_prefix}")
                super(AsyncAccountAdapter, self).send_mail(template_prefix, email, context)
                logger.info(f"Confirmation email sent successfully to {email}")
            except Exception:
                logger.exception("Failed to send confirmation email to %s", email)
            return
        
        # For other emails, send asynchronously
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
    
    def send_confirmation_mail(self, request, emailconfirmation, signup):
        """
        Send confirmation email synchronously to ensure confirmation is saved
        before the email is sent. This is critical for verification links to work.
        Handles both HMAC-based confirmations (virtual) and database-backed confirmations.
        """
        if not emailconfirmation.email_address.email:
            logger.info("Skipping confirmation email send for user without email")
            return
        
        # Check if this is an HMAC confirmation (virtual, no pk) or database confirmation
        is_hmac = not hasattr(emailconfirmation, 'pk') or emailconfirmation.pk is None
        
        # Ensure EmailAddress is saved first
        if hasattr(emailconfirmation.email_address, 'pk') and not emailconfirmation.email_address.pk:
            emailconfirmation.email_address.save()
            logger.info(f"Saved EmailAddress {emailconfirmation.email_address.id} for {emailconfirmation.email_address.email}")
        
        # For database confirmations, ensure it's saved
        if not is_hmac:
            if not emailconfirmation.pk:
                emailconfirmation.save()
                logger.info(f"Saved EmailConfirmation {emailconfirmation.id} with key {emailconfirmation.key[:30]}...")
            # Refresh to ensure we have the latest data
            emailconfirmation.refresh_from_db()
        
        # Verify the confirmation can be found by key BEFORE sending email
        try:
            from allauth.account.models import EmailConfirmation
            test_found = EmailConfirmation.from_key(emailconfirmation.key)
            if not is_hmac and hasattr(test_found, 'id'):
                if test_found.id != emailconfirmation.id:
                    logger.error(f"WARNING: Confirmation key lookup returned different ID! Expected {emailconfirmation.id}, got {test_found.id}")
                else:
                    logger.info(f"Verified confirmation {emailconfirmation.id} can be found by key before sending email")
            else:
                logger.info(f"Verified HMAC confirmation can be found by key before sending email")
        except Exception as e:
            logger.error(f"ERROR: Cannot find confirmation by key before sending email! Key: {emailconfirmation.key[:30]}..., Error: {e}")
        
        # Build context - use self to get URL (respects site settings)
        activate_url = self.get_email_confirmation_url(request, emailconfirmation)
        logger.info(f"Generated confirmation URL: {activate_url}")
        
        ctx = {
            "user": emailconfirmation.email_address.user,
            "activate_url": activate_url,
            "key": emailconfirmation.key,
            "request": request,
        }
        
        # Ensure user display name is in context
        if 'user' in ctx and ctx['user']:
            if not hasattr(ctx['user'], 'display_name'):
                try:
                    ctx['user_display_name'] = ctx['user'].get_display_name()
                except Exception:
                    ctx['user_display_name'] = ctx['user'].username or 'Perekas kasutaja'
        
        # Send email synchronously using parent's send_mail (not async)
        # This ensures the confirmation is fully saved before email is sent
        template_prefix = "account/email/email_confirmation"
        try:
            # Use parent's send_mail directly to bypass async behavior
            super(AsyncAccountAdapter, self).send_mail(template_prefix, emailconfirmation.email_address.email, ctx)
            logger.info(f"Confirmation email sent synchronously to {emailconfirmation.email_address.email} for user {emailconfirmation.email_address.user_id}, key: {emailconfirmation.key[:30]}...")
        except Exception:
            logger.exception("Failed to send confirmation email to %s", emailconfirmation.email_address.email)

