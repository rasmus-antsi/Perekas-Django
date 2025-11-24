"""
Middleware to check email verification and redirect users who haven't verified their email.
"""
from django.shortcuts import redirect
from allauth.account.models import EmailAddress


class EmailVerificationMiddleware:
    """
    Middleware that checks if authenticated users have verified their email.
    Redirects to verification page if email is not verified.
    Only applies to users with email addresses (children without email are exempt).
    """
    
    # URLs that don't require email verification
    EXEMPT_URLS = [
        '/W01-d8/',  # Admin panel
        '/accounts/logout/',
        '/accounts/email/',
        '/accounts/confirm-email/',
        '/accounts/verification-sent/',
        '/family/resend-verification/',
        '/account/login/',
        '/account/signup/',
        '/accounts/password/reset/',
        '/accounts/password/reset/done/',
        '/accounts/password/reset/key/',
        '/accounts/password/reset/key/done/',
        '/accounts/confirm-email/',
        '/static/',
        '/media/',
    ]
    
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        # Check if user is authenticated and has an email
        if request.user.is_authenticated and request.user.email:
            # Check if current path is exempt
            if not any(request.path.startswith(exempt) for exempt in self.EXEMPT_URLS):
                # Check if email is verified
                try:
                    email_address = EmailAddress.objects.filter(
                        user=request.user,
                        email=request.user.email,
                        primary=True
                    ).first()
                    
                    if email_address and not email_address.verified:
                        # Email exists but not verified - redirect to verification page
                        # Always redirect to verification sent page, which will handle resending
                        from django.urls import reverse
                        return redirect('account_verification_sent')
                except Exception:
                    # If there's an error checking, allow access
                    pass
        
        response = self.get_response(request)
        return response
