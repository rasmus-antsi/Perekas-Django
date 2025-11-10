from django.urls import path

from . import views

app_name = 'a_rewards'

urlpatterns = [
    path('', views.index, name='index'),
]

