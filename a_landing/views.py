from django.shortcuts import render, redirect
from django.contrib import messages
from django.conf import settings
from time import time
import logging

from .forms import ReviewForm
from .models import ReviewFormSubmission
from a_family.emails import _send_branded_email, _get_logo_url

logger = logging.getLogger(__name__)


# Create your views here.
def index(request):
    return render(request, 'a_landing/index.html', {'timestamp': int(time())})


def features(request):
    # Redirect to main page - JavaScript will handle anchor scrolling
    return redirect('a_landing:landing_index')


def about(request):
    # Redirect to main page - JavaScript will handle anchor scrolling
    return redirect('a_landing:landing_index')


def plans(request):
    # Redirect to main page - JavaScript will handle anchor scrolling
    return redirect('a_landing:landing_index')


def privacy_policy(request):
    return render(request, 'a_landing/privacy_policy.html')


def terms_of_service(request):
    return render(request, 'a_landing/terms_of_service.html')


def review_form(request):
    """View for the review form to collect feedback from users who didn't use the app."""
    if request.method == 'POST':
        form = ReviewForm(request.POST)
        if form.is_valid():
            submission = form.save(commit=False)
            
            # Link to user if authenticated
            if request.user.is_authenticated:
                submission.user = request.user
            
            # Get IP address
            x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
            if x_forwarded_for:
                ip_address = x_forwarded_for.split(',')[0]
            else:
                ip_address = request.META.get('REMOTE_ADDR')
            submission.ip_address = ip_address
            
            submission.save()
            
            # Send email notification to admin
            try:
                admin_email = getattr(settings, 'REVIEW_FORM_ADMIN_EMAIL', 'info@perekas.ee')
                logo_url = _get_logo_url(request)
                
                context = {
                    'submission': submission,
                    'user': submission.user,
                    'user_name': submission.user.get_display_name() if submission.user else None,
                    'email': submission.email,
                    'name': submission.name or 'Nimi pole määratud',
                    'why_created_account': submission.why_created_account,
                    'added_family_members': submission.added_family_members,
                    'created_tasks': submission.created_tasks,
                    'created_rewards': submission.created_rewards,
                    'created_shopping_lists': submission.created_shopping_lists,
                    'what_prevented_usage': submission.what_prevented_usage or 'Pole määratud',
                    'feedback': submission.feedback or 'Pole määratud',
                    'submitted_at': submission.submitted_at,
                    'ip_address': submission.ip_address,
                    'logo_url': logo_url,
                }
                
                # Send to both admin email and rasmus435@icloud.com for review
                recipients = [admin_email, 'rasmus435@icloud.com']
                
                _send_branded_email(
                    subject=f"[Perekas] Uus tagasiside: {submission.email}",
                    template_name='email/review_form_submission.html',
                    context=context,
                    recipients=recipients,
                )
            except Exception as e:
                logger.exception("Failed to send review form submission email: %s", e)
            
            messages.success(request, 'Täname tagasiside eest! Sinu vastus on salvestatud.')
            return redirect('a_landing:review_form')
    else:
        form = ReviewForm()
        # Pre-fill email if user is authenticated
        if request.user.is_authenticated and request.user.email:
            form.fields['email'].initial = request.user.email
            form.fields['name'].initial = request.user.get_display_name()
    
    return render(request, 'a_landing/review_form.html', {
        'form': form,
        'timestamp': int(time()),
    })