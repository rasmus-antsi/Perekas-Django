from django.urls import path
from . import views

app_name = 'a_subscription'

urlpatterns = [
    path('success/', views.upgrade_success, name='upgrade_success'),
    path('webhook/', views.webhook, name='webhook'),
]

