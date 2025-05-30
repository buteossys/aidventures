from django.urls import path
from django.contrib.auth.views import LogoutView
from . import views

app_name = 'access'

urlpatterns = [
    path('', views.access_view, name='access'),
    path('login/', views.login_view, name='login'), # URL for the login page at /access/login/
    path('register/', views.register_view, name='register'),
    path('subscribe/', views.subscribe_view, name='subscribe'),
    path('forgot-password/', views.forgot_password_view, name='forgot-password'), # URL for forgot password page at /access/forgot-password/
    path('reset-password/<str:uidb64>/<str:token>/', views.reset_password_view, name='reset-password'),
    path('user-home/<int:user_id>/', views.home, name='user-home'),
    path('contact/', views.contact_view, name='contact'),
    path('contact_success/', views.contact_success_view, name='contact_success'),
    path('logout/', LogoutView.as_view(
        next_page='/access/login/',
        template_name='access/login.html'
    ), name='logout'),
    path('create-checkout-session/', views.create_stripe_checkout_session, name='create-checkout-session'),
    path('webhook/', views.stripe_webhook, name='stripe_webhook'),
    path('payment/success/', views.payment_success, name='payment-success'),
    path('payment/cancel/', views.payment_cancel, name='payment-cancel'),
    path('verify-email/<str:uidb64>/<str:token>/', views.verify_email_view, name='verify-email'),
    path('resend-verification/', views.resend_verification_view, name='resend-verification'),
]