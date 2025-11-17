from django.urls import path

from . import views

app_name = 'a_family'

urlpatterns = [
    path('onboarding/', views.onboarding, name='onboarding'),
    path('remove/<int:user_id>/', views.remove_member, name='remove_member'),
    path('', views.index, name='index'),
]

