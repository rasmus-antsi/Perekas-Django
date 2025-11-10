from django.urls import path

from . import views

app_name = 'a_landing'

urlpatterns = [
    path('', views.index, name='landing_index'),
]