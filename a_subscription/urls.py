from django.urls import path
from . import views

app_name = 'a_subscription'

urlpatterns = [
    path('status/', views.subscription_status, name='status'),
    path('upgrade/', views.upgrade, name='upgrade'),
    path('success/', views.upgrade_success, name='upgrade_success'),
    path('cancel/', views.cancel, name='cancel'),
    path('webhook/', views.webhook, name='webhook'),
]

