from django.db import models
from django.contrib.auth.models import User, AbstractUser
from django.core.validators import EmailValidator, RegexValidator

# Create your models here.

class ContactModel(models.Model):
    name = models.CharField(default='Your Name', max_length=100)
    sender = models.EmailField(default='Your Email')
    message = models.CharField(default='Your Message',max_length=300)
    cc_myself = models.BooleanField()

class User(AbstractUser):
    email_verified = models.BooleanField(default=False)
    email_verification_token = models.CharField(max_length=255, blank=True, null=True)
    email_verification_sent_at = models.DateTimeField(null=True, blank=True)

    # Fix the reverse accessor clash
    groups = models.ManyToManyField(
        'auth.Group',
        verbose_name='groups',
        blank=True,
        related_name='custom_user_set',  # Add unique related_name
        related_query_name='custom_user'
    )
    user_permissions = models.ManyToManyField(
        'auth.Permission',
        verbose_name='user permissions',
        blank=True,
        related_name='custom_user_set',  # Add unique related_name
        related_query_name='custom_user'
    )

    class Meta:
        verbose_name = 'user'
        verbose_name_plural = 'users'