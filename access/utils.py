from django.contrib.auth.tokens import default_token_generator
from django.utils.http import urlsafe_base64_encode
from django.utils.encoding import force_bytes
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils import timezone
from django.urls import reverse
from datetime import timedelta
import logging
from django.conf import settings
logger = logging.getLogger(__name__)

def send_verification_email(request, user):
    """Send verification email to user"""
    # Generate verification token
    token = default_token_generator.make_token(user)
    uid = urlsafe_base64_encode(force_bytes(user.pk))
    
    # Save token and timestamp
    user.email_verification_token = token
    user.email_verification_sent_at = timezone.now()
    user.save()

    # Build verification URL using SITE_URL
    verify_url = f"{settings.SITE_URL}{reverse('access:verify-email', kwargs={'uidb64': uid, 'token': token})}"

    # Prepare email context
    context = {
        'user': user,
        'verify_url': verify_url,
        'site_name': 'AIdventures',
        'expiry_hours': 24  # Token expiry time in hours
    }

    # Render email templates
    email_html = render_to_string('access/emails/verify_email.html', context)
    email_text = render_to_string('access/emails/verify_email.txt', context)
    logger.info(f"Sending verification email to {user.email} with {email_html} and {email_text}")
    # Send email
    send_mail(
        'Verify Your Email Address',
        email_text,
        settings.DEFAULT_FROM_EMAIL,
        [user.email],
        html_message=email_html,
        fail_silently=False,
    )
    logger.info(f"Verification email sent to {user.email}")

def is_verification_token_expired(user):
    """Check if verification token is expired"""
    if not user.email_verification_sent_at:
        return True
    expiry_time = user.email_verification_sent_at + timedelta(hours=24)
    return timezone.now() > expiry_time
