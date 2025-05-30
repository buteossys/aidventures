from django.urls import path
from . import views

app_name = 'gemini'

urlpatterns = [
    path('review_choices/', views.review_choices, name='review_choices'),
    path('review_choices/<int:adventure_id>/', views.review_choices, name='review_choices'),
    path('main_prompt/', views.main_prompt_view, name='main_prompt'),
    path('wait-for-story/<int:story_id>/', views.wait_for_story, name='wait_for_story'),
    path('stories/<int:story_id>/status/', views.check_story_status, name='check_story_status'),
]