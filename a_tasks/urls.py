from django.urls import path

from . import views

app_name = 'a_tasks'

urlpatterns = [
    path('', views.index, name='index'),
    path('cron/create-recurring-tasks', views.create_recurring_tasks_endpoint, name='create_recurring_tasks_cron'),
]