from django.urls import path
from . import views

app_name = 'user_profile'

urlpatterns = [
    path('profile/', views.profile_view, name='profile'),
    path('change-subscription/', views.change_subscription, name='change_subscription'),
    path('subscription-success/', views.subscription_success, name='subscription_success'),
    path('friends/', views.friends_view, name='friends'),
    path('terms/', views.terms_view, name='terms'),
    path('hints/', views.hints_view, name='hints'),
    path('faq/', views.faq_view, name='faq'),
]