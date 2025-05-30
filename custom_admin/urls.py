from django.urls import path
from . import views

app_name = 'custom_admin'

urlpatterns = [
    path('', views.admin_dashboard, name='dashboard'),
    path('modify-user/<int:user_id>/', views.modify_user_profile, name='modify_user_profile'),
    path('delete-user/<int:user_id>/', views.delete_user, name='delete_user'),
    path('get-instances/', views.get_model_instances, name='get_instances'),
    path('get-instance-data/', views.get_instance_data, name='get_instance_data'),
    path('get-adventure-stories/', views.get_adventure_stories, name='get_adventure_stories'),
    path('list/<str:model_name>/', views.list_data, name='list_data'),
    path('view/<str:model_name>/<int:pk>/', views.view_data, name='view_data'),
    path('create/user/', views.create_user, name='create_user'),
    path('delete/', views.delete_data, name='delete_data'),
    path('get_adventure_details/<int:adventure_id>/', views.get_adventure_details, name='get_adventure_details'),
    path('get_story_details/<int:story_id>/', views.get_story_details, name='get_story_details'),
    path('update_story_status/<int:story_id>/', views.update_story_status, name='update_story_status'),
]
