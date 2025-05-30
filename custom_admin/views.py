from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import user_passes_test
from django.contrib.admin.views.decorators import staff_member_required
from django.apps import apps
from django.http import JsonResponse
from django.contrib.auth import get_user_model
from access.models import ContactModel
from gemini.models import Adventure, Story, StoryImages, ChapterImage
from user_profile.models import UserProfile
from django.views.decorators.http import require_POST
from django.contrib import messages
from django.shortcuts import redirect
from django.utils import timezone
from django.contrib.auth.forms import UserCreationForm
from django.db.models import Count, Q
from django.core.paginator import Paginator
from django.http import HttpResponseForbidden, HttpResponseNotAllowed
import json
import logging
from google.cloud import storage
from django.contrib.auth import authenticate, login

# Get the custom User model
User = get_user_model()

logger = logging.getLogger(__name__)

def is_approved_admin(user):
    if not user.is_authenticated:
        return False
    return user.email == 'recdohbargus@gmail.com' or user.is_superuser

@user_passes_test(is_approved_admin, login_url='/access/login/')
def admin_dashboard(request):
    """Enhanced dashboard view with more statistics and user management."""
    # Get counts for dashboard statistics
    user_count = User.objects.count()
    adventure_count = Adventure.objects.count()
    story_count = Story.objects.count()
    
    # Get users with their story counts
    users = User.objects.annotate(
        story_count=Count('adventures__stories')
    ).prefetch_related('adventures', 'profile')
    
    return render(request, 'custom_admin/dashboard.html', {
        'user_count': user_count,
        'adventure_count': adventure_count,
        'story_count': story_count,
        'users': users,
    })

@user_passes_test(is_approved_admin, login_url='/access/login/')
def get_model_instances(request):
    model_path = request.GET.get('model')
    if not model_path:
        return JsonResponse({'error': 'Model not specified'}, status=400)
    
    try:
        app_label, model_name = model_path.split('.')
        instances = None
        
        if app_label == 'auth' and model_name == 'User':
            instances = User.objects.all().prefetch_related('profile')
        elif app_label == 'user_profile' and model_name == 'UserProfile':
            instances = UserProfile.objects.all().select_related('user')
        elif app_label == 'gemini':
            if model_name == 'Adventure':
                instances = Adventure.objects.all().select_related('user')
            elif model_name == 'Story':
                instances = Story.objects.all().select_related('adventure')
            elif model_name == 'StoryImages':
                instances = StoryImages.objects.all().select_related('story')
        
        if instances is None:
            return JsonResponse({'error': 'Invalid model'}, status=400)
        
        instances_data = [{
            'id': instance.pk,
            'str_representation': str(instance),
        } for instance in instances]
        
        return JsonResponse({'instances': instances_data})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)

@user_passes_test(is_approved_admin, login_url='/access/login/')
def get_instance_data(request):
    model_path = request.GET.get('model')
    instance_id = request.GET.get('id')
    
    if not model_path or not instance_id:
        return JsonResponse({'error': 'Model and ID required'}, status=400)
    
    try:
        app_label, model_name = model_path.split('.')
        data = {}
        
        if app_label == 'auth' and model_name == 'User':
            user = User.objects.get(pk=instance_id)
            data = {
                'username': user.username,
                'email': user.email,
                'date_joined': str(user.date_joined),
                'last_login': str(user.last_login),
                'is_active': user.is_active,
                'profile': {
                    'tier': user.profile.tier,
                    'subscription_date': str(user.profile.subscription_date),
                    'stories_created': user.profile.stories_created,
                    'is_active': user.profile.is_active
                } if hasattr(user, 'profile') else None
            }
            
        elif app_label == 'gemini':
            if model_name == 'Adventure':
                adventure = Adventure.objects.get(pk=instance_id)
                data = {
                    'user': adventure.user.username,
                    'adventure_number': adventure.adventure_number,
                    'created_at': str(adventure.created_at),
                    'world_data': adventure.world_data,
                    'character_data': adventure.character_data,
                    'setting_data': adventure.setting_data
                }
            elif model_name == 'Story':
                story = Story.objects.get(pk=instance_id)
                data = {
                    'title': story.title,
                    'adventure': story.adventure.id,
                    'status': story.status,
                    'created_at': str(story.created_at),
                    'updated_at': str(story.updated_at),
                    'summary': story.summary,
                    'input_token_count': story.input_token_count,
                    'output_token_count': story.output_token_count
                }
        
        return JsonResponse({'data': data})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)

@user_passes_test(is_approved_admin, login_url='/access/login/')
def get_adventure_stories(request):
    adventure_id = request.GET.get('adventure_id')
    if not adventure_id:
        return JsonResponse({'error': 'Adventure ID required'}, status=400)
    
    try:
        stories = Story.objects.filter(adventure_id=adventure_id).prefetch_related(
            'story_images',
            'story_images__chapter_images'
        )
        stories_data = []
        
        for story in stories:
            story_data = {
                'id': story.id,
                'created_at': str(story.created_at),
                'updated_at': str(story.updated_at),
                'title': story.title,
                'summary': story.summary,
                'input_token_count': story.input_token_count,
                'output_token_count': story.output_token_count,
                'status': story.status,
                'images': {
                    'cover_image': None,
                    'chapter_images': []
                }
            }
            
            # Get story images if they exist
            try:
                if hasattr(story, 'story_images'):
                    story_images = story.story_images
                    if story_images.cover_image:
                        story_data['images']['cover_image'] = story_images.cover_image.url
                    
                    # Get chapter images
                    chapter_images = story_images.chapter_images.all()
                    story_data['images']['chapter_images'] = [
                        {
                            'url': img.image.url,
                            'chapter': img.chapter_number,
                            'text_marker': img.text_marker
                        } for img in chapter_images
                    ]
            except Exception as e:
                print(f"Error accessing images for story {story.id}: {str(e)}")
            
            stories_data.append(story_data)
        
        return JsonResponse({'stories': stories_data})
    except Exception as e:
        print(f"Error in get_adventure_stories: {str(e)}")
        return JsonResponse({'error': str(e)}, status=400)

@user_passes_test(is_approved_admin, login_url='/access/login/')
def modify_user_profile(request, user_id):
    user = get_object_or_404(User.objects.select_related('profile'), id=user_id)
    
    if request.method == 'POST':
        form_type = request.POST.get('form_type')
        
        try:
            if form_type == 'user':
                # Update User data
                user.username = request.POST.get('username', user.username)
                user.email = request.POST.get('email', user.email)
                user.first_name = request.POST.get('first_name', user.first_name)
                user.last_name = request.POST.get('last_name', user.last_name)
                user.is_active = request.POST.get('is_active') == 'true'
                user.is_staff = request.POST.get('is_staff') == 'true'
                user.save()
                
            elif form_type == 'profile':
                # Update Profile data
                profile = user.profile
                profile.name = request.POST.get('name', profile.name)
                profile.tier = request.POST.get('tier', profile.tier)
                profile.stories_created = int(request.POST.get('stories_created', profile.stories_created))
                profile.is_active = request.POST.get('profile_is_active') == 'true'
                profile.stripe_customer_id = request.POST.get('stripe_customer_id', profile.stripe_customer_id)
                profile.stripe_subscription_id = request.POST.get('stripe_subscription_id', profile.stripe_subscription_id)
                
                subscription_date = request.POST.get('subscription_date')
                if subscription_date:
                    profile.subscription_date = subscription_date
                
                profile.save()
            
            messages.success(request, f'Profile updated successfully for user {user.username}')
            
        except Exception as e:
            messages.error(request, f'Error updating profile: {str(e)}')
    
    # Get all adventures for this user with their stories and related data
    adventures = Adventure.objects.filter(user=user).prefetch_related(
        'stories',
        'stories__content',
        'stories__story_images',
        'stories__story_images__chapter_images'
    ).order_by('-created_at')
    
    adventures_data = []
    for adventure in adventures:
        stories_data = []
        for story in adventure.stories.all():
            # Get story images info
            has_images = False
            if hasattr(story, 'story_images'):
                has_images = bool(story.story_images.cover_image) or story.story_images.chapter_images.exists()

            # Get audio info
            audio_info = {'exists': False, 'size': 0}
            try:
                storage_client = storage.Client()
                bucket = storage_client.bucket('write-audio')
                filename = f"{user.id}_{adventure.id}_{story.id}_audio.mp3"
                blob = bucket.blob(filename)
                if blob.exists():
                    audio_info = {
                        'exists': True,
                        'size': blob.size
                    }
            except Exception as e:
                logger.error(f"Error checking audio for story {story.id}: {e}")

            stories_data.append({
                'id': story.id,
                'title': story.title,
                'created_at': story.created_at,
                'updated_at': story.updated_at,
                'input_token_count': story.input_token_count,
                'output_token_count': story.output_token_count,
                'status': story.status,
                'error': story.error,
                'has_images': has_images,
                'audio': audio_info,
                'audio_voice': story.audio_voice,
                'content': story.content.raw_content if hasattr(story, 'content') else None,
                'story_images': getattr(story, 'story_images', None)
            })

        adventure_data = {
            'id': adventure.id,
            'created_at': adventure.created_at,
            'updated_at': adventure.updated_at,
            'adventure_number': adventure.adventure_number,
            'style_data': adventure.style_data,
            'world_data': adventure.world_data,
            'character_data': adventure.character_data,
            'setting_data': adventure.setting_data,
            'stories': stories_data
        }
        adventures_data.append(adventure_data)

    return render(request, 'custom_admin/modify_profile.html', {
        'user': user,
        'profile': user.profile,
        'adventures_data': adventures_data,
        'status_choices': Story.STATUS_CHOICES,
    })

@user_passes_test(is_approved_admin, login_url='/access/login/')
def get_adventure_details(request, adventure_id):
    """Fetch details for a specific adventure"""
    try:
        adventure = Adventure.objects.filter(id=adventure_id).first()
        if not adventure:
            logger.error(f"Adventure {adventure_id} not found")
            return JsonResponse({'error': f'Adventure {adventure_id} not found'}, status=404)
        
        # Get stories with related data
        stories = Story.objects.filter(adventure_id=adventure_id).select_related(
            'content',
            'story_images'
        ).prefetch_related(
            'story_images__chapter_images'
        )
        
        stories_data = []
        for story in stories:
            stories_data.append({
                'id': story.id,
                'title': story.title,
                'status': story.status,
                'created_at': story.created_at,
                'updated_at': story.updated_at,
                'input_token_count': story.input_token_count,
                'output_token_count': story.output_token_count,
                'audio_voice': story.audio_voice,
                'content': story.content.raw_content if hasattr(story, 'content') else None,
                'story_images': {
                    'cover_image': story.story_images.cover_image.url if hasattr(story, 'story_images') and story.story_images.cover_image else None,
                    'chapter_images': [
                        {
                            'part_key': img.part_key,
                            'chapter_key': img.chapter_key,
                            'image_url': img.image.url,
                            'text_marker': img.text_marker
                        } for img in story.story_images.chapter_images.all() if hasattr(story, 'story_images')
                    ]
                }
            })

        data = {
            'id': adventure.id,
            'created_at': adventure.created_at.isoformat(),
            'updated_at': adventure.updated_at.isoformat(),
            'adventure_number': adventure.adventure_number,
            'style_data': adventure.style_data,
            'world_data': adventure.world_data,
            'character_data': adventure.character_data,
            'setting_data': adventure.setting_data,
            'stories': stories_data
        }
        
        return JsonResponse(data)
    except Exception as e:
        logger.error(f"Error in get_adventure_details: {str(e)}")
        return JsonResponse({
            'error': str(e),
            'error_type': type(e).__name__,
            'error_location': 'get_adventure_details'
        }, status=500)

@user_passes_test(is_approved_admin, login_url='/access/login/')
def get_story_details(request, story_id):
    story = get_object_or_404(Story.objects.select_related(
        'content',
        'story_images'
    ).prefetch_related(
        'story_images__chapter_images'
    ), id=story_id)
    
    # Get story images info
    has_images = False
    if hasattr(story, 'story_images'):
        has_images = bool(story.story_images.cover_image) or story.story_images.chapter_images.exists()

    # Get audio info
    audio_info = {'exists': False, 'size': 0}
    try:
        storage_client = storage.Client()
        bucket = storage_client.bucket('write-audio')
        filename = f"{story.adventure.user.id}_{story.adventure.id}_{story.id}_audio.mp3"
        blob = bucket.blob(filename)
        if blob.exists():
            audio_info = {
                'exists': True,
                'size': blob.size
            }
    except Exception as e:
        logger.error(f"Error checking audio for story {story.id}: {e}")

    data = {
        'id': story.id,
        'title': story.title,
        'created_at': story.created_at,
        'updated_at': story.updated_at,
        'input_token_count': story.input_token_count,
        'output_token_count': story.output_token_count,
        'status': story.status,
        'error': story.error,
        'has_images': has_images,
        'audio': audio_info,
        'audio_voice': story.audio_voice,
        'content': story.content.raw_content if hasattr(story, 'content') else None,
        'story_images': {
            'cover_image': story.story_images.cover_image.url if hasattr(story, 'story_images') and story.story_images.cover_image else None,
            'chapter_images': [
                {
                    'part_key': img.part_key,
                    'chapter_key': img.chapter_key,
                    'image_url': img.image.url,
                    'text_marker': img.text_marker
                } for img in story.story_images.chapter_images.all() if hasattr(story, 'story_images')
            ]
        }
    }
    
    return JsonResponse(data)

@user_passes_test(is_approved_admin, login_url='/access/login/')
def list_data(request, model_name):
    """View to list instances of a specific model."""
    page = request.GET.get('page', 1)
    search = request.GET.get('search', '')
    
    if model_name == 'user':
        items = User.objects.all()
        if search:
            items = items.filter(
                Q(username__icontains=search) | 
                Q(email__icontains=search)
            )
    elif model_name == 'adventure':
        items = Adventure.objects.select_related('user')
        if search:
            items = items.filter(world_data__icontains=search)
    elif model_name == 'story':
        items = Story.objects.select_related('adventure__user')
        if search:
            items = items.filter(
                Q(title__icontains=search) | 
                Q(summary__icontains=search)
            )
    else:
        return HttpResponseForbidden("Invalid model name")
    
    # Add proper ordering
    items = items.order_by('-id')
    
    paginator = Paginator(items, 20)  # 20 items per page
    page_obj = paginator.get_page(page)
    
    return render(request, 'custom_admin/list_data.html', {
        'page_obj': page_obj,
        'model_name': model_name,
        'search': search
    })

@user_passes_test(is_approved_admin, login_url='/access/login/')
def view_data(request, model_name, pk):
    """View to display detailed information about a specific instance."""
    if model_name == 'user':
        item = get_object_or_404(User.objects.prefetch_related(
            'adventures',
            'adventures__stories'
        ), pk=pk)
    elif model_name == 'adventure':
        item = get_object_or_404(Adventure.objects.select_related('user').prefetch_related(
            'stories',
            'stories__story_images'
        ), pk=pk)
    elif model_name == 'story':
        item = get_object_or_404(Story.objects.select_related(
            'adventure__user',
            'story_images'
        ), pk=pk)
    else:
        return HttpResponseForbidden("Invalid model name")
    
    return render(request, 'custom_admin/view_data.html', {
        'item': item,
        'model_name': model_name
    })

@user_passes_test(is_approved_admin, login_url='/access/login/')
def create_user(request):
    """View to create a new user."""
    if request.method == 'POST':
        form = UserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            # Create associated UserProfile
            UserProfile.objects.create(
                user=user,
                tier='free',
                subscription_date=timezone.now(),
                stories_created=0,
                is_active=True
            )
            messages.success(request, f'User {user.username} created successfully')
            return redirect('custom_admin:dashboard')
    else:
        form = UserCreationForm()
    
    return render(request, 'custom_admin/create_user.html', {'form': form})

@user_passes_test(is_approved_admin, login_url='/access/login/')
@require_POST
def delete_data(request):
    """View to delete a model instance."""
    model_name = request.GET.get('model')
    instance_id = request.GET.get('id')
    
    try:
        if model_name == 'user':
            user = get_object_or_404(User, pk=instance_id)
            username = user.username
            user.delete()
            messages.success(request, f'User {username} deleted successfully')
        elif model_name == 'adventure':
            adventure = get_object_or_404(Adventure, pk=instance_id)
            adventure.delete()
            messages.success(request, f'Adventure {instance_id} deleted successfully')
        elif model_name == 'story':
            story = get_object_or_404(Story, pk=instance_id)
            story.delete()
            messages.success(request, f'Story {story.title} deleted successfully')
        else:
            return JsonResponse({'success': False, 'error': 'Invalid model name'})
        
        return JsonResponse({'success': True})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})

@user_passes_test(is_approved_admin, login_url='/access/login/')
@require_POST
def delete_user(request, user_id):
    """View to delete a user and all their related data."""
    try:
        user = get_object_or_404(User, id=user_id)
        username = user.username
        user.delete()
        messages.success(request, f'User {username} deleted successfully')
        return JsonResponse({'success': True})
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=400)

@user_passes_test(is_approved_admin, login_url='/access/login/')
def update_story_status(request, story_id):
    if request.method == 'POST':
        try:
            story = get_object_or_404(Story, id=story_id)
            new_status = request.POST.get('status')
            
            # Validate the status is one of the allowed choices
            if new_status in dict(Story.STATUS_CHOICES):
                story.status = new_status
                story.save()
                messages.success(request, f'Status updated for Story #{story_id}')
            else:
                messages.error(request, 'Invalid status value')
                
            # Redirect back to the user profile page
            return redirect('custom_admin:modify_user_profile', user_id=story.adventure.user.id)
            
        except Exception as e:
            messages.error(request, f'Error updating status: {str(e)}')
            return redirect('custom_admin:modify_user_profile', user_id=story.adventure.user.id)
    
    return HttpResponseNotAllowed(['POST'])
