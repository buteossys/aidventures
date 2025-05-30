from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from user_profile.models import UserProfile

class Command(BaseCommand):
    help = 'Updates a user\'s Stripe validation status'

    def add_arguments(self, parser):
        parser.add_argument('email', type=str, help='Email of the user to update')
        parser.add_argument('--stripe-customer-id', type=str, help='Stripe customer ID')
        parser.add_argument('--stripe-subscription-id', type=str, help='Stripe subscription ID')

    def handle(self, *args, **options):
        try:
            user = User.objects.get(email=options['email'])
            profile = UserProfile.objects.get(user=user)
            
            if options['stripe_customer_id']:
                profile.stripe_customer_id = options['stripe_customer_id']
            if options['stripe_subscription_id']:
                profile.stripe_subscription_id = options['stripe_subscription_id']
            
            profile.save()
            self.stdout.write(self.style.SUCCESS(f'Successfully updated Stripe validation for user {user.email}'))
            
        except User.DoesNotExist:
            self.stdout.write(self.style.ERROR(f'User with email {options["email"]} not found'))
        except UserProfile.DoesNotExist:
            self.stdout.write(self.style.ERROR(f'UserProfile for {options["email"]} not found')) 