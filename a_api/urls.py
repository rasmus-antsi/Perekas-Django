from django.urls import path
from . import views

app_name = 'a_api'

urlpatterns = [
    # Authentication
    path('login/', views.login, name='login'),
    path('logout/', views.logout, name='logout'),
    path('user/', views.get_user, name='user'),
    path('register/', views.register, name='register'),
    
    # Tasks
    path('tasks/', views.get_tasks, name='tasks'),
    path('tasks/create/', views.create_task, name='create_task'),
    path('tasks/<int:task_id>/', views.update_task, name='update_task'),
    path('tasks/<int:task_id>/start/', views.start_task, name='start_task'),
    path('tasks/<int:task_id>/cancel/', views.cancel_task, name='cancel_task'),
    path('tasks/<int:task_id>/complete/', views.complete_task, name='complete_task'),
    path('tasks/<int:task_id>/approve/', views.approve_task, name='approve_task'),
    path('tasks/<int:task_id>/unapprove/', views.unapprove_task, name='unapprove_task'),
    path('tasks/<int:task_id>/delete/', views.delete_task, name='delete_task'),
    
    # Rewards
    path('rewards/', views.get_rewards, name='rewards'),
    path('rewards/create/', views.create_reward, name='create_reward'),
    path('rewards/<int:reward_id>/claim/', views.claim_reward, name='claim_reward'),
    
    # Family
    path('family/', views.get_family, name='family'),
    path('family/join/', views.join_family, name='join_family'),
    
    # Dashboard
    path('dashboard/', views.get_dashboard, name='dashboard'),
    
    # Shopping List
    path('shopping/', views.get_shopping_list, name='shopping'),
    path('shopping/create/', views.create_shopping_item, name='create_shopping_item'),
    path('shopping/<int:item_id>/', views.update_shopping_item, name='update_shopping_item'),
    path('shopping/<int:item_id>/delete/', views.delete_shopping_item, name='delete_shopping_item'),
]

