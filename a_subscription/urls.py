from django.urls import path
from django.views.decorators.csrf import csrf_exempt
from . import views

app_name = 'a_subscription'

urlpatterns = [
    path('success/', views.upgrade_success, name='upgrade_success'),
    path('webhook/', views.webhook, name='webhook'),
    path('webhook', views.webhook, name='webhook_no_slash'),  # Accept without trailing slash for Stripe
]

