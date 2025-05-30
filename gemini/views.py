from django.shortcuts import render, redirect, get_object_or_404
from .forms import (
    StyleForm, 
    WorldForm, 
    CharacterFormSetHelper, 
    SettingFormSetHelper, 
    StoryPromptForm,
    get_character_formset,
    get_setting_formset,
    CharacterBaseForm,
    SettingBaseForm
)
from django.contrib.auth.decorators import login_required
from .models import (
    Adventure, Style, World, Character, Setting, Story,
    age_group_choices, style_gender_choices, genre_choices,
    tone_choices, temporal_choices, StoryImages, ChapterImage
)
from django.http import JsonResponse
from django.urls import reverse
from .genai_utils import *
from django.contrib import messages
import json
from django.utils import timezone
from django.views.decorators.http import require_http_methods
from django.core.exceptions import ValidationError
from django.forms import formset_factory
from django.db import transaction  # Add this import at the top
import logging
import traceback
from django.core.files.base import ContentFile
from main_app.tts_utils import synthesize_long_text, get_available_voices
from gemini.tier_utils import check_access, thread_check_access, check_free_tier_limit
from django.contrib.auth import get_user_model

# Set up logger
logger = logging.getLogger('ganai')

User = get_user_model()

# Create your views here.

@login_required
def review_choices(request, adventure_id=None):
    """Handle both new story and add to world flows"""
    source = request.GET.get('source', 'new_story')
    adventure_id = adventure_id or request.session.get('adventure_id')
    
    if not adventure_id:
        messages.error(request, "No adventure specified")
        return redirect('main_app:home')
        
    adventure = get_object_or_404(Adventure, id=adventure_id, user=request.user)
    
    # Get the formset classes first
    CharacterFormSet = get_character_formset(adventure=adventure)
    SettingFormSet = get_setting_formset(adventure=adventure)
    
    # Create the layout helpers
    character_helper = CharacterFormSetHelper()
    setting_helper = SettingFormSetHelper()
    
    if request.method == 'POST':
        if 'back' in request.POST:
            # Clean up the adventure instance if going back
            if source != 'library':
                adventure.delete()
            return redirect('main_app:home')
        
        if 'confirm' in request.POST:
            try:
                # First create the formsets with the POST data
                character_formset = CharacterFormSet(request.POST, prefix='character')
                setting_formset = SettingFormSet(request.POST, prefix='setting')

                # Debug character formset validation
                print("\nDEBUG: Character Formset Data")
                print(f"Is valid: {character_formset.is_valid()}")
                print(f"Total forms: {character_formset.total_form_count()}")
                print(f"Management form data: {character_formset.management_form.data}")
                for i, form in enumerate(character_formset):
                    print(f"Character {i} errors: {form.errors}")
                    print(f"Character {i} data: {form.data}")

                # Debug setting formset validation
                print("\nDEBUG: Setting Formset Data")
                print(f"Is valid: {setting_formset.is_valid()}")
                print(f"Total forms: {setting_formset.total_form_count()}")
                print(f"Management form data: {setting_formset.management_form.data}")
                for i, form in enumerate(setting_formset):
                    print(f"Setting {i} errors: {form.errors}")
                    print(f"Setting {i} data: {form.data}")

                # Then process the data
                adventure.character_data = [
                    {
                        **form.cleaned_data,
                        'description': (
                            next((c.get('description', '') for c in adventure.character_data if c.get('id') == form.cleaned_data.get('id')), '')
                            + '\n\n' + form.cleaned_data.get('description', '')
                        ).strip(),
                        'about': (
                            next((c.get('about', '') for c in adventure.character_data if c.get('id') == form.cleaned_data.get('id')), '')
                            + '\n\n' + form.cleaned_data.get('about', '')
                        ).strip()
                    }
                    for form in character_formset 
                    if form.cleaned_data
                ]
                adventure.setting_data = [
                    {
                        **form.cleaned_data,
                        'about': (
                            next((s.get('about', '') for s in adventure.setting_data if s.get('id') == form.cleaned_data.get('id')), '')
                            + '\n\n' + form.cleaned_data.get('about', '')
                        ).strip()
                    }
                    for form in setting_formset 
                    if form.cleaned_data
                ]

                # Update all adventure fields directly from form data
                print("\nDEBUG: Style Data in POST")
                print("age_group:", request.POST.get('age_group'))
                print("gender:", request.POST.get('gender'))
                print("genre:", request.POST.get('genre'))
                print("tone:", request.POST.get('tone'))
                
                print("\nDEBUG: Current Adventure Style Data")
                print("Before update:", adventure.style_data)
                
                adventure.style_data = {
                    'age_group': request.POST.get('age_group') or adventure.style_data.get('age_group', ''),
                    'gender': request.POST.get('gender') or adventure.style_data.get('gender', ''),
                    'genre': request.POST.get('genre') or adventure.style_data.get('genre', ''),
                    'tone': request.POST.get('tone') or adventure.style_data.get('tone', '')
                }
                
                print("After update:", adventure.style_data)
                adventure.world_data = {
                    'temporal': request.POST.get('temporal') or adventure.world_data.get('temporal', ''),
                    'name': request.POST.get('name') or adventure.world_data.get('name', ''),
                    'general': (adventure.world_data.get('general', '') + '\n\n' + request.POST.get('general', '')).strip(),
                    'backstory': (adventure.world_data.get('backstory', '') + '\n\n' + request.POST.get('backstory', '')).strip(),
                    'current_events': (adventure.world_data.get('current_events', '') + '\n\n' + request.POST.get('current_events', '')).strip()
                }
                
                adventure.save()

                print("DEBUG: Final character_data:", adventure.character_data)
                print("DEBUG: Final setting_data:", adventure.setting_data)

                # Redirect based on source
                if source == 'library':
                    return redirect('main_app:library')
                else:
                    return redirect('gemini:main_prompt')

            except Exception as e:
                messages.error(request, f"Error updating adventure: {str(e)}")
                return redirect('main_app:home')
        
        # Handle GET request
    if request.method == 'GET':
        if source == 'library':
            # Pre-populate forms with existing adventure data
            character_formset = CharacterFormSet(
                prefix='character',
                initial=adventure.character_data,
                form_kwargs={'adventure': adventure}
            )
            setting_formset = SettingFormSet(
                prefix='setting',
                initial=adventure.setting_data,
                form_kwargs={'adventure': adventure}
            )
            
            context = {
                'source': source,
                'adventure': adventure,
                'style_data': adventure.style_data,
                'world_data': adventure.world_data,
                'world_form': WorldForm(instance=adventure.world if hasattr(adventure, 'world') else None),
                'characters': adventure.character_data,
                'settings': adventure.setting_data,
                'character_formset': character_formset,
                'character_formset_helper': character_helper,
                'setting_formset': setting_formset,
                'setting_formset_helper': setting_helper,
                'age_group_choices': age_group_choices,
                'style_gender_choices': style_gender_choices,
                'genre_choices': genre_choices,
                'tone_choices': tone_choices,
                'temporal_choices': temporal_choices
            }
        else:
            # Create empty formsets for new story
            character_formset = CharacterFormSet(prefix='character')
            setting_formset = SettingFormSet(prefix='setting')
            
            context = {
                'source': source,
                'style_data': {},
                'world_data': {},
                'world_form': WorldForm(),
                'characters': [],
                'settings': [],
                'character_formset': character_formset,
                'character_formset_helper': character_helper,
                'setting_formset': setting_formset,
                'setting_formset_helper': setting_helper,
                'age_group_choices': age_group_choices,
                'style_gender_choices': style_gender_choices,
                'genre_choices': genre_choices,
                'tone_choices': tone_choices,
                'temporal_choices': temporal_choices
            }
    else:
        # Create empty formsets for new story
        character_formset = CharacterFormSet(prefix='character')
        setting_formset = SettingFormSet(prefix='setting')
        
        # Create the layout helpers
        character_helper = CharacterFormSetHelper()
        setting_helper = SettingFormSetHelper()
        
        # Display the review page with empty forms
        context = {
            'source': source,
            'style_data': {},
            'world_data': {},
            'world_form': WorldForm(),
            'characters': [],
            'settings': [],
            'character_formset': character_formset,
            'character_formset_helper': character_helper,
            'setting_formset': setting_formset,
            'setting_formset_helper': setting_helper,
            'age_group_choices': age_group_choices,
            'style_gender_choices': style_gender_choices,
            'genre_choices': genre_choices,
            'tone_choices': tone_choices,
            'temporal_choices': temporal_choices
        }
    
    return render(request, 'gemini/review_choices.html', context)

@login_required
def main_prompt_view(request):
    """Handle story prompt submission and generation"""
    adventure_id = request.GET.get('adventure_id') or request.session.get('adventure_id')
    
    if not adventure_id:
        messages.error(request, "No adventure specified")
        return redirect('main_app:library')
    
    try:
        adventure = Adventure.objects.get(id=adventure_id, user=request.user)
        
        if request.method == 'POST':
            form = StoryPromptForm(request.POST)
            if form.is_valid():
                # Create and save the story first
                story = form.save(commit=False)
                story.adventure = adventure
                story.title = f"Story {adventure.stories.count() + 1}"
                story.status = 'processing'
                story.save()

                # Clean up session if needed
                if 'adventure_id' in request.session:
                    del request.session['adventure_id']

                # Start the generation process in the background
                try:
                    # Use a background task or thread to generate the story
                    from threading import Thread
                    Thread(target=generate_story, args=(adventure.id,)).start()
                except Exception as e:
                    logger.error(f"Failed to start story generation: {str(e)}")
                    # Don't return error here, let the user see the waiting page anyway
                
                # Redirect to waiting page immediately
                return JsonResponse({
                    'status': 'success',
                    'redirect_url': reverse('gemini:wait_for_story', args=[story.id])
                })
            else:
                return JsonResponse({
                    'status': 'error',
                    'message': 'Invalid form data'
                }, status=400)
        
        else:
            form = StoryPromptForm()
            stories = Story.objects.filter(
                adventure=adventure,
                status='completed'
            ).order_by('-created_at')
            
            # Add debug prints
            print("Adventure data debug:")
            print(f"Style data: {adventure.style_data}")
            print(f"World data: {adventure.world_data}")
            print(f"Character data: {adventure.character_data}")
            print(f"Setting data: {adventure.setting_data}")
            
            context = {
                'form': form,
                'adventure': adventure,
                'stories': stories,
                'story_data': {
                    'style': adventure.style_data,
                    'world': adventure.world_data,
                    'characters': adventure.character_data,
                    'settings': adventure.setting_data,
                }
            }
            
            # Debug the context
            print("\nContext story_data debug:")
            print(f"Style in context: {context['story_data']['style']}")
            print(f"Characters in context: {context['story_data']['characters']}")
            print(f"Settings in context: {context['story_data']['settings']}")
            
            return render(request, 'gemini/main_prompt.html', context)
    
    except Adventure.DoesNotExist:
        messages.error(request, "Adventure not found")
        return redirect('main_app:library')

@login_required
def wait_for_story(request, story_id):
    """
    View to handle waiting for story generation and displaying results.
    """
    try:
        story = Story.objects.get(id=story_id, adventure__user=request.user)
        
        context = {
            'story': story,  # This is what we use in the template
            'status': story.status,
        }
        
        logger.info(f"Story {story_id} status: {story.status}")
        return render(request, 'gemini/wait_for_story.html', context)
        
    except Story.DoesNotExist:
        messages.error(request, 'Story not found.')
        return redirect('gemini:main_prompt')

@login_required
def check_story_status(request, story_id):
    """Check the status of a story generation."""
    try:
        story = Story.objects.get(id=story_id, adventure__user=request.user)
        
        response_data = {
            'status': story.status,
            'error': story.error if story.status == 'failed' else None
        }
        
        # Add redirect URL if story is completed
        if story.status == 'completed':
            response_data['redirect_url'] = reverse('gemini:wait_for_story', args=[story_id])
            
        return JsonResponse(response_data)
        
    except Story.DoesNotExist:
        return JsonResponse({
            'status': 'error', 
            'message': 'Story not found'
        }, status=404)
    except Exception as e:
        logger.error(f"Error checking story status: {str(e)}")
        return JsonResponse({
            'status': 'failed',
            'error': 'An unexpected error occurred'
        }, status=500)

@login_required
def view_story(request, story_id):
    try:
        story = Story.objects.get(id=story_id, adventure__user=request.user)
        context = {
            'story': story,
            'adventure': story.adventure
        }
        return render(request, 'gemini/view_story.html', context)
    except Story.DoesNotExist:
        return redirect('gemini:main_prompt')



def get_character_formset(adventure=None):
    max_num = 7 if adventure and adventure.stories.exists() else 3
    return formset_factory(
        CharacterBaseForm,
        extra=1,
        max_num=max_num,
        validate_max=True
    )

def get_setting_formset(adventure=None):
    max_num = 7 if adventure and adventure.stories.exists() else 3
    return formset_factory(
        SettingBaseForm,
        extra=1,
        max_num=max_num,
        validate_max=True
    )


@thread_check_access
def generate_story(adventure_id):
    try:
        # Get all processing stories for this adventure
        processing_stories = Story.objects.filter(
            adventure_id=adventure_id, 
            status='processing'
        )
        
        if processing_stories.count() > 1:
            # If multiple processing stories exist, mark all but the most recent as failed
            latest_story = processing_stories.order_by('-created_at').first()
            processing_stories.exclude(id=latest_story.id).update(
                status='failed',
                raw_file='Story generation cancelled - duplicate processing story found'
            )
            story = latest_story
        elif processing_stories.count() == 1:
            story = processing_stories.first()
        else:
            logger.error(f"No processing story found for adventure {adventure_id}")
            return JsonResponse({
                'status': 'error',
                'message': 'No processing story found'
            }, status=404)

        prompt = story.prompt
        prompt_token_count = 0
        candidates_token_count = 0
        try:
            # Configure Gemini
            google_api_key = get_secret('GOOGLE_API_KEY')
            if not google_api_key:
                raise ValueError("Failed to retrieve GOOGLE_API_KEY from Secret Manager")
            genai.configure(api_key=google_api_key)
            
            # Step 1: Prepare adventure data
            logger.debug("Preparing adventure data...")
            cache_data, age_group = prepare_adventure_data(adventure_id)
            logger.debug(f"Adventure data prepared with age_group: {age_group}")
            
            # Step 2: Create chat context
            logger.debug("Creating chat context...")
            chat, cache_prompt_count, cache_candidates_count = create_cache(cache_data)
            prompt_token_count += cache_prompt_count
            candidates_token_count += cache_candidates_count
            logger.debug("Chat context created successfully")
            
            # Step 3: Generate and validate outline
            logger.debug("Getting outline...")
            outline, chat, outline_prompt_count, outline_candidates_count = get_outline(prompt, chat, age_group, story)
            prompt_token_count += outline_prompt_count
            candidates_token_count += outline_candidates_count
            logger.debug("Outline generated successfully")
            
            # Step 4: Generate the story
            logger.debug("Generating story content...")
            story_prompt_count, story_candidates_count = write_story(outline, age_group, chat, prompt, story)
            prompt_token_count += story_prompt_count
            candidates_token_count += story_candidates_count
            logger.debug("Story content generated successfully")
            logger.debug(f"Total prompt tokens: {prompt_token_count}")
            logger.debug(f"Total candidates tokens: {candidates_token_count}")
            # Update the story instance with the generated content
            story.status = 'completed'
            story.input_token_count = prompt_token_count
            story.output_token_count = candidates_token_count
            story.save()
            
            logger.info(f"Successfully generated story for adventure {adventure_id}")
            return JsonResponse({'status': 'success'})
            
        except Exception as e:
            logger.error(f"Error in story generation process: {str(e)}", exc_info=True)
            story.status = 'failed'
            story.raw_file = f"Story generation failed: {str(e)}"
            story.save()
            return JsonResponse({
                'status': 'error',
                'message': str(e)
            }, status=500)
            
    except Exception as e:
        logger.error(f"Error in story management process: {str(e)}", exc_info=True)
        return JsonResponse({
            'status': 'error',
            'message': str(e)
        }, status=500)

        
    except Story.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': 'Story not found'}, status=404)
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)


