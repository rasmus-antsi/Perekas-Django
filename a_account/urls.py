from django.urls import path
from . import views

app_name = 'a_account'

urlpatterns = [
    path('settings/', views.settings_base, name='settings'),
    path('settings/general/', views.general_settings, name='general'),
    path('settings/notifications/', views.notification_settings, name='notifications'),
    path('settings/subscriptions/', views.subscription_settings, name='subscriptions'),
    path('transfer-ownership/', views.transfer_ownership, name='transfer_ownership'),
    path('delete-account/', views.delete_account, name='delete_account'),
]

