"""
URL configuration for _core project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include
from django.shortcuts import render, redirect
from django.conf import settings
from django.conf.urls.static import static

def handler404(request, exception):
    """Custom 404 error handler"""
    return render(request, '404.html', status=404)

def handler500(request):
    """Custom 500 error handler"""
    return render(request, '500.html', status=500)

def redirect_account_email_to_settings(request):
    """Redirect authenticated users from /accounts/email to settings"""
    if request.user.is_authenticated:
        return redirect('a_account:settings')
    # For unauthenticated users, use the default allauth email view
    from allauth.account.views import EmailView
    return EmailView.as_view()(request)

from a_family import views as family_views
from . import views as core_views

urlpatterns = [
    path('W01-d8/', admin.site.urls),
    path('health/', core_views.health_check, name='health_check'),
    # Override account_email to redirect authenticated users to settings
    path('accounts/email/', redirect_account_email_to_settings, name='account_email'),
    # Override account_verification_sent to use custom view
    path('accounts/verification-sent/', family_views.verification_sent, name='account_verification_sent'),
    path('accounts/', include('allauth.urls')),
    path('family/', include('a_family.urls')),
    path('dashboard/', include('a_dashboard.urls')),
    path('account/', include('a_account.urls')),
    path('subscription/', include('a_subscription.urls')),
    path('shopping/', include('a_shopping.urls')),
    path('rewards/', include('a_rewards.urls')),
    path('tasks/', include('a_tasks.urls')),
    path('', include('a_landing.urls')),
]

# Serve media files in development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
