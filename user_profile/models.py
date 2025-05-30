from django.db import models
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.core.validators import EmailValidator, RegexValidator
import logging
from django.conf import settings

logger = logging.getLogger(__name__)

class UserProfile(models.Model):
    TIER_CHOICES = [
        ('free', 'Free'),
        ('daily', 'Daily'),
        ('family', 'Family'),
        ('unlimited', 'Unlimited')
    ]

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='profile'
    )
    name = models.CharField(max_length=20, blank=True)
    #phone_number = models.CharField(
     #   max_length=15, 
      #  blank=True,
       # validators=[RegexValidator(
        #    regex=r'^\+?1?\d{9,15}$',
        #    message='Phone number must be entered in the format: +999999999. Up to 15 digits allowed.'
        #   )]
    #)
    tier = models.CharField(max_length=10, choices=TIER_CHOICES, default='free')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    stories_created = models.IntegerField(default=0)
    is_active = models.BooleanField(default=True)
    stripe_customer_id = models.CharField(max_length=100, blank=True, null=True)
    stripe_subscription_id = models.CharField(max_length=100, blank=True, null=True)
    subscription_date = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"{self.user.username}'s Profile - {self.tier.title()}"

# Remove the post_save signals for now since we'll handle profile creation manually
