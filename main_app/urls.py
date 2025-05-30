from django.urls import path, include
from . import views

app_name = 'main_app'

urlpatterns = [
    path('', views.home_view, name='home'),
    path('library/', views.library_view, name='library'),
    path('recent/', views.recent_view, name='recent'),
    path('popular/', views.popular_view, name='popular'),
    path('message/', views.message_view, name='message'),
    path('share/', views.share_view, name='share'),
    path('user_profile/', include('user_profile.urls')),
    path('gemini/', include('gemini.urls')),
    path('access/', include('access.urls')),
    path('start_new_adventure/', views.start_new_adventure, name='start_new_adventure'),
    path('generate_audio/<int:story_id>/', views.generate_audio, name='generate_audio'),
    path('check_audio/<int:story_id>/', views.check_audio, name='check_audio'),
    path('story_images/<int:story_id>/', views.story_images, name='story_images'),
    path('check_story_file/<int:story_id>/', views.check_story_file, name='check_story_file'),
    path('create_final_story/<int:story_id>/', views.create_final_story, name='create_final_story'),
    path('get_story_content/<int:story_id>/', views.get_story_content, name='get_story_content'),
    path('update_story_content/<int:story_id>/', views.update_story_content, name='update_story_content'),
]