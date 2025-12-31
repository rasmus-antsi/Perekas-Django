from django.urls import path

from . import views

app_name = 'a_landing'

urlpatterns = [
    path('', views.index, name='landing_index'),
    path('features/', views.features, name='features'),
    path('about/', views.about, name='about'),
    path('plans/', views.plans, name='plans'),
    path('privacy-policy/', views.privacy_policy, name='privacy_policy'),
    path('terms-of-service/', views.terms_of_service, name='terms_of_service'),
    path('review/', views.review_form, name='review_form'),
]