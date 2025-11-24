from django.urls import path

from . import views

app_name = 'a_family'

urlpatterns = [
    path('onboarding/', views.onboarding, name='onboarding'),
    path('remove/<int:user_id>/', views.remove_member, name='remove_member'),
    path('resend-verification/', views.resend_verification_email, name='resend_verification'),
    path('manage-child/<int:child_id>/', views.manage_child_account, name='manage_child_account'),
    path('', views.index, name='index'),
]

