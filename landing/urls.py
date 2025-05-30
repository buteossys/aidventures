from django.urls import path, include
from . import views

app_name = 'landing'

urlpatterns = [
    path('', views.landing_view, name='landing'),
    path('access/', include('access.urls')),
]