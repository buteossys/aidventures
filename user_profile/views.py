from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .forms import ProfileEditForm
import stripe
from django.conf import settings
from django.http import JsonResponse
from django.urls import reverse
from .models import UserProfile

stripe.api_key = settings.STRIPE_SECRET_KEY

# Create your views here.
@login_required
def profile_view(request):
    if request.method == 'POST':
        form = ProfileEditForm(request.POST, user=request.user)
        if form.is_valid():
            # Update user fields
            user = request.user
            user.first_name = form.cleaned_data['first_name']
            user.last_name = form.cleaned_data['last_name']
            user.username = form.cleaned_data['username']
            user.email = form.cleaned_data['email']
            
            # Update profile fields except tier
            profile = user.profile
            profile.save()

    else:
        form = ProfileEditForm(user=request.user)
    
    context = {
        'form': form,
        'user': request.user,
        'profile': request.user.profile,
        }
    return render(request, 'user_profile/profile.html', context)

def friends_view(request):
    return render(request, 'user_profile/friends.html')

def terms_view(request):
    return render(request, 'user_profile/terms.html')

def faq_view(request):
    return render(request, 'user_profile/faq.html')

def hints_view(request):
    return render(request, 'user_profile/hints.html')

@login_required
def change_subscription(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    
    try:
        new_tier = request.POST.get('tier')
        if not new_tier or new_tier not in dict(UserProfile.TIER_CHOICES):
            return JsonResponse({'error': 'Invalid tier selected'}, status=400)

        # Get the price ID for the new tier
        price_id = settings.STRIPE_PRICE_IDS.get(new_tier)
        if not price_id:
            return JsonResponse({'error': 'Invalid tier selected'}, status=400)

        user = request.user
        profile = user.profile

        if new_tier == 'free':
            # Handle downgrade to free tier
            if profile.stripe_subscription_id:
                # Cancel the existing subscription
                subscription = stripe.Subscription.retrieve(profile.stripe_subscription_id)
                subscription.cancel_at_period_end = True
                subscription.save()
            
            return JsonResponse({
                'status': 'success',
                'message': 'Your subscription will be cancelled at the end of the billing period'
            })

        # Create a new checkout session
        success_url = request.build_absolute_uri(reverse('user_profile:subscription_success'))
        cancel_url = request.build_absolute_uri(reverse('user_profile:profile'))

        if profile.stripe_customer_id:
            # Existing customer - create a subscription change session
            session = stripe.checkout.Session.create(
                customer=profile.stripe_customer_id,
                payment_method_types=['card'],
                mode='subscription',
                line_items=[{
                    'price': price_id,
                    'quantity': 1,
                }],
                success_url=success_url,
                cancel_url=cancel_url,
                metadata={
                    'user_id': user.id,
                    'new_tier': new_tier
                }
            )
        else:
            # New customer
            session = stripe.checkout.Session.create(
                payment_method_types=['card'],
                mode='subscription',
                line_items=[{
                    'price': price_id,
                    'quantity': 1,
                }],
                success_url=success_url,
                cancel_url=cancel_url,
                metadata={
                    'user_id': user.id,
                    'new_tier': new_tier
                }
            )

        return JsonResponse({
            'status': 'success',
            'session_id': session.id
        })

    except Exception as e:
        return JsonResponse({
            'error': str(e)
        }, status=500)

@login_required
def subscription_success(request):
    messages.success(request, 'Your subscription has been updated successfully!')
    return redirect('user_profile:profile')