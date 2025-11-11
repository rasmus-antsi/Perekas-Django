from django.urls import path

from . import views

app_name = 'a_landing'

urlpatterns = [
    path('', views.index, name='landing_index'),
    path('features/', views.features, name='features'),
    path('about/', views.about, name='about'),
    path('plans/', views.plans, name='plans'),
]