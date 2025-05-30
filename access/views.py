from django.shortcuts import render, redirect, get_object_or_404
from django.http import HttpResponse, JsonResponse  # Import HttpResponse for now
from django.core.mail import send_mail
from .models import ContactModel
from django.contrib.auth import authenticate, login, get_user_model
from django.contrib.auth.forms import UserCreationForm
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from .forms import RegistrationForm, ContactForm, ForgotPasswordForm, ResetPasswordForm
from user_profile.models import UserProfile
from django.db import transaction, IntegrityError
from django.utils import timezone
from django.conf import settings
import stripe
from django.views.decorators.csrf import csrf_exempt
from django.urls import reverse
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode
from django.utils.encoding import force_str, force_bytes
from django.contrib.auth.tokens import default_token_generator
from django.template.loader import render_to_string
import logging
from .utils import send_verification_email, is_verification_token_expired
from urllib.parse import urlencode

stripe.api_key = settings.STRIPE_SECRET_KEY

User = get_user_model()
logger = logging.getLogger(__name__)

def access_view(request):
    return render(request, 'access/access.html')
 
def login_view(request):
    source = request.GET.get('source')  # Get the source parameter
    if request.method == 'POST':
        username = request.POST['username']
        password = request.POST['password']
        user = authenticate(request, username=username, password=password)
        if user is not None:
            # Allow superusers to bypass email verification
            if user.is_superuser or user.email_verified:
                login(request, user)
                return redirect('main_app:home')
            else:
                messages.error(request, 'Please verify your email before logging in. Check your inbox for the verification link.')
                return redirect('access:login')
        else:
            messages.error(request, 'Invalid username or password.')
    return render(request, 'access/login.html', {'source': source})  # Pass source to template
    
def register_view(request):
    source = request.GET.get('source')
    
    if request.method == 'POST':
        form = RegistrationForm(request.POST)
        if form.is_valid():  # This will run all validations before any DB operations
            try:
                with transaction.atomic():
                    # Create the user
                    user = User.objects.create_user(
                        username=form.cleaned_data['username'],
                        email=form.cleaned_data['email'],
                        password=form.cleaned_data['password'],
                    )
                    
                    # Create the profile
                    profile = UserProfile.objects.create(
                        user=user,
                        name=form.cleaned_data['name'],
                        stories_created=0,
                        is_active=True
                    )

                    if source == 'free':
                        profile.tier = 'free'
                        profile.save()
                        send_verification_email(request, user)
                        messages.success(request, 'Registration successful! Please check your email to verify your account.')
                        return redirect(f"{reverse('access:login')}?source=free")
                    else:
                        login(request, user)
                        return redirect('access:subscribe')
                        
            except Exception as e:
                # If something fails after validations, rollback everything
                messages.error(request, f"Registration failed: {str(e)}")
                return render(request, 'access/register.html', {'form': form, 'source': source})
    else:
        form = RegistrationForm()
    
    return render(request, 'access/register.html', {'form': form, 'source': source})

def forgot_password_view(request):
    if request.method == 'POST':
        form = ForgotPasswordForm(request.POST)
        if form.is_valid():
            email = form.cleaned_data['email']
            try:
                user = User.objects.get(email=email)
                
                # Generate password reset token
                token = default_token_generator.make_token(user)
                uid = urlsafe_base64_encode(force_bytes(user.pk))
                
                # Build reset URL
                reset_url = f"{settings.SITE_URL}{reverse('access:reset-password', kwargs={'uidb64': uid, 'token': token})}"
                
                # Prepare email context
                context = {
                    'user': user,
                    'reset_url': reset_url,
                    'site_name': 'AIdventures',
                }
                
                # Render email template
                email_html = render_to_string('access/emails/password_reset_email.html', context)
                email_text = render_to_string('access/emails/password_reset_email.txt', context)
                
                # Send email
                send_mail(
                    'Password Reset Request',
                    email_text,
                    settings.DEFAULT_FROM_EMAIL,
                    [user.email],
                    html_message=email_html,
                    fail_silently=False,
                )
                
                messages.success(
                    request,
                    "If an account exists with this email, you will receive password reset instructions."
                )
                return redirect('access:login')
                
            except User.DoesNotExist:
                # Don't reveal that the user doesn't exist
                messages.success(
                    request,
                    "If an account exists with this email, you will receive password reset instructions."
                )
                return redirect('access:login')
                
            except Exception as e:
                logger.error(f"Password reset email failed: {str(e)}")
                messages.error(
                    request,
                    "There was an error processing your request. Please try again later."
                )
    else:
        form = ForgotPasswordForm()
    
    return render(request, 'access/forgot_password.html', {'form': form})

@login_required
def home(request, user_id=None):
   # If no user_id is provided or if it doesn't match the logged-in user,
    # redirect to the correct user home page
    if user_id is None or user_id != request.user.id:
        return redirect('access:user-home', user_id=request.user.id)
    
    context = {
        'user_id': request.user.id,
        'user': request.user,
        'profile': request.user.profile
         #We can add recent stories later when that functionality is implemented
        #'recent_stories': Adventure.objects.filter(user=request.user).order_by('-id')[:5]
    }
    return render(request, 'main_app/home.html', context)

def contact_success_view(request):
    return render(request, 'access/contact_success.html')

def contact_view(request):
    if request.method == 'POST':
        form = ContactForm(request.POST)
        if form.is_valid():
            try:
                # Save the contact form data first
                contact = form.save()
                
                # Get the values from the correct field names
                user_name = form.cleaned_data.get('name', '')
                user_email = form.cleaned_data.get('sender', '')  # Changed from 'email' to 'sender'
                user_message = form.cleaned_data.get('message', '')
                
                # Prepare admin email
                admin_subject = f"New Contact Form Submission from {user_name}"
                admin_message = f"""
                Name: {user_name}
                Email: {user_email}
                
                Message:
                {user_message}
                """
                
                # Send email to admin
                send_mail(
                    subject=admin_subject,
                    message=admin_message,
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[settings.ADMIN_EMAIL],
                    fail_silently=False,
                )
                
                # If user wants to receive a copy (cc_myself)
                if form.cleaned_data.get('cc_myself'):
                    # Prepare and send confirmation email to user
                    user_subject = "Thank you for contacting AIdventures"
                    user_message = f"""
                    Dear {user_name},
                    
                    Thank you for reaching out to us. We have received your message and will get back to you as soon as possible.
                    
                    Your message:
                    {user_message}
                    
                    Best regards,
                    The AIdventures Team
                    """
                    
                    send_mail(
                        subject=user_subject,
                        message=user_message,
                        from_email=settings.DEFAULT_FROM_EMAIL,
                        recipient_list=[user_email],
                        fail_silently=False,
                    )
                
                messages.success(request, 'Thank you for your message! We will get back to you soon.')
                return redirect('access:contact_success')
                
            except Exception as e:
                print(f"Email sending failed: {str(e)}")
                messages.error(request, 'There was an error sending your message. Please try again later.')
                return render(request, 'access/contact.html', {'form': form})
    else:
        form = ContactForm()
    
    return render(request, 'access/contact.html', {'form': form})

def create_stripe_checkout_session(request):
    if request.method == 'POST':
        try:
            # Get tier and user data from the request
            tier = request.POST.get('tier')
            user_id = request.POST.get('user_id')
            
            # Get the appropriate price ID
            price_id = settings.STRIPE_PRICE_IDS.get(tier)
            if not price_id:
                return JsonResponse({'error': 'Invalid tier selected'}, status=400)

            # Create Stripe checkout session
            checkout_session = stripe.checkout.Session.create(
                payment_method_types=['card'],
                line_items=[{
                    'price': price_id,
                    'quantity': 1,
                }],
                mode='subscription',
                success_url=settings.STRIPE_SUCCESS_URL + f'?session_id={{CHECKOUT_SESSION_ID}}&user_id={user_id}',
                cancel_url=settings.STRIPE_CANCEL_URL + f'?user_id={user_id}',
                client_reference_id=str(user_id),
                metadata={
                    'tier': tier,
                    'user_id': user_id
                }
            )
            
            return JsonResponse({'sessionId': checkout_session.id})
            
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=400)
    
    return JsonResponse({'error': 'Invalid request method'}, status=400)

@csrf_exempt
def stripe_webhook(request):
    payload = request.body
    sig_header = request.META['HTTP_STRIPE_SIGNATURE']
    event = None

    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, settings.STRIPE_WEBHOOK_SECRET
        )
    except ValueError as e:
        return HttpResponse(status=400)
    except stripe.error.SignatureVerificationError as e:
        return HttpResponse(status=400)

    if event['type'] == 'checkout.session.completed':
        session = event['data']['object']
        user_id = session['metadata'].get('user_id')
        new_tier = session['metadata'].get('new_tier')
        
        if user_id and new_tier:
            try:
                user = User.objects.get(id=user_id)
                profile = user.profile
                profile.tier = new_tier
                profile.stripe_customer_id = session.get('customer')
                profile.stripe_subscription_id = session.get('subscription')
                profile.save()
                
                # Log the successful tier update
                logger.info(f"User {user_id} tier updated to {new_tier} via Stripe webhook")
            except User.DoesNotExist:
                logger.error(f"User {user_id} not found during webhook processing")
            except Exception as e:
                logger.error(f"Error updating user {user_id} tier: {str(e)}")

    elif event['type'] == 'customer.subscription.updated':
        subscription = event['data']['object']
        customer_id = subscription['customer']
        
        try:
            profile = UserProfile.objects.get(stripe_customer_id=customer_id)
            # Update subscription status
            profile.stripe_subscription_id = subscription['id']
            profile.save()
            
            # Log the subscription update
            logger.info(f"Subscription updated for customer {customer_id}")
        except UserProfile.DoesNotExist:
            logger.error(f"Profile not found for customer {customer_id}")
        except Exception as e:
            logger.error(f"Error updating subscription for customer {customer_id}: {str(e)}")

    return HttpResponse(status=200)

def payment_success(request):
    session_id = request.GET.get('session_id')
    user_id = request.GET.get('user_id')
    
    try:
        # Verify the session
        session = stripe.checkout.Session.retrieve(session_id)
        if session.payment_status == 'paid':
            # Log the user in and redirect to home
            user = User.objects.get(id=user_id)
            login(request, user)
            messages.success(request, 'Payment successful! Welcome to AIdventures!')
            return redirect('main_app:home')
    except Exception as e:
        messages.error(request, 'There was an error processing your payment.')
    
    return redirect('access:login')

def payment_cancel(request):
    user_id = request.GET.get('user_id')
    try:
        # Delete the user if they cancelled during initial registration
        User.objects.filter(id=user_id).delete()
        messages.info(request, 'Payment cancelled. Please try again.')
    except Exception as e:
        messages.error(request, 'There was an error cancelling your registration.')
    
    return redirect('access:register')

def subscribe_view(request):
    return render(request, 'access/subscribe.html')

def reset_password_view(request, uidb64, token):
    try:
        uid = force_str(urlsafe_base64_decode(uidb64))
        user = User.objects.get(pk=uid)
    except (TypeError, ValueError, OverflowError, User.DoesNotExist):
        user = None

    if user is not None and default_token_generator.check_token(user, token):
        if request.method == 'POST':
            form = ResetPasswordForm(request.POST)
            if form.is_valid():
                # Set new password
                user.set_password(form.cleaned_data['password'])
                user.save()
                messages.success(request, "Your password has been reset successfully. You can now login.")
                return redirect('access:login')
        else:
            form = ResetPasswordForm()
        return render(request, 'access/reset_password.html', {'form': form})
    else:
        messages.error(request, "The password reset link is invalid or has expired.")
        return redirect('access:login')

def verify_email_view(request, uidb64, token):
    try:
        uid = force_str(urlsafe_base64_decode(uidb64))
        user = User.objects.get(pk=uid)
    except (TypeError, ValueError, OverflowError, User.DoesNotExist):
        user = None

    if user and not user.email_verified and user.email_verification_token == token:
        if is_verification_token_expired(user):
            messages.error(
                request,
                "The verification link has expired. Please request a new one."
            )
            return redirect('access:resend-verification')

        user.email_verified = True
        user.email_verification_token = None
        user.save()
        messages.success(
            request,
            "Email verified successfully! You can now log in to your account."
        )
        return redirect('access:login')
    else:
        messages.error(
            request,
            "The verification link is invalid or has already been used."
        )
        return redirect('access:login')

def resend_verification_view(request):
    if request.method == 'POST':
        email = request.POST.get('email')
        try:
            user = User.objects.get(email=email, email_verified=False)
            # Generate new verification token
            token = default_token_generator.make_token(user)
            uid = urlsafe_base64_encode(force_bytes(user.pk))
            
            # Save token and timestamp
            user.email_verification_token = token
            user.email_verification_sent_at = timezone.now()
            user.save()

            # Build verification URL
            verify_url = request.build_absolute_uri(
                reverse('access:verify-email', kwargs={'uidb64': uid, 'token': token})
            )

            # Prepare email context
            context = {
                'user': user,
                'verify_url': verify_url,
                'site_name': 'AIdventures',
                'expiry_hours': 24
            }

            # Render email templates
            email_html = render_to_string('access/emails/verify_email.html', context)
            email_text = render_to_string('access/emails/verify_email.txt', context)

            # Send email
            send_mail(
                'Verify Your Email Address',
                email_text,
                settings.DEFAULT_FROM_EMAIL,
                [user.email],
                html_message=email_html,
                fail_silently=False,
            )

            messages.success(
                request,
                "Verification email has been resent. Please check your inbox."
            )
        except User.DoesNotExist:
            # Don't reveal if the email exists
            messages.success(
                request,
                "If an unverified account exists with this email, "
                "a verification link will be sent."
            )
        return redirect('access:login')

    return render(request, 'access/resend_verification.html')