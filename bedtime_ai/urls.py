"""
URL configuration for bedtime_ai project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.1/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
import os
from django.http import HttpResponse

def health_check(request):
    return HttpResponse("OK")

def warmup(request):
    """App Engine warmup handler
    See https://cloud.google.com/appengine/docs/standard/python3/configuring-warmup-requests"""
    return HttpResponse('OK')

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('landing.urls')),
    path('access/', include('access.urls')),
    path('main_app/', include('main_app.urls')),
    path('user_profile/', include('user_profile.urls')),
    path('gemini/', include('gemini.urls')),
    path('custom-admin/', include('custom_admin.urls')),
    path('_ah/health', health_check),  # App Engine health check
    path('_ah/warmup', warmup),
]

# Serve media files in development
if not os.getenv('GAE_APPLICATION'):
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

