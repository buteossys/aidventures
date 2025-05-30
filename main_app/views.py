from django.shortcuts import render
#from .models import Story  # Import your Story model
from django.http import HttpResponse, JsonResponse
from django.contrib.auth.decorators import login_required
from gemini.models import Adventure, Story  # Import from gemini app instead of main_app
import json
from django.views.decorators.csrf import ensure_csrf_cookie
from django.utils import timezone
from django.utils.decorators import method_decorator
from time import sleep
from django.contrib import messages
from django.shortcuts import redirect
from django.db import transaction
from main_app.tts_utils import get_available_voices
from django.core.files.base import ContentFile
from django.views.decorators.http import require_http_methods
from .tts_utils import synthesize_long_text, split_text_into_chunks
import os
from google.cloud import storage, texttospeech
import logging
from typing import List
import io
import threading
from django.conf import settings
from gemini.img_utils import get_stored_image
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image, PageBreak
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from urllib.request import urlretrieve
import tempfile
from PIL import Image as PILImage  # Add this to avoid conflict with reportlab Image
from reportlab.lib.utils import ImageReader
from reportlab.lib.pagesizes import letter



logger = logging.getLogger(__name__)

@login_required
def home_view(request):
    sleep(0.1)  # Add a small delay to ensure database connection is ready
    user = request.user
    adventures = Adventure.objects.filter(user=request.user).prefetch_related('stories').order_by('-created_at')
    
    library_items = []
    for adventure in adventures:
        stories = Story.objects.filter(
            adventure=adventure,
            status='completed'
        ).order_by('-created_at')
        
        for story in stories:
            # Parse the outline JSON if it's stored as a JSON string
            try:
                outline = json.loads(story.outline) if story.outline else "No outline available"
            except json.JSONDecodeError:
                outline = story.outline  # Use as is if it's not JSON
                
            library_items.append({
                'title': story.title,
                'created_at': story.created_at,
                'updated_at': story.updated_at,
                'summary': outline,
                'story_id': story.id,
                'adventure_id': adventure.id,
                'status': story.status,
                'cover_image_url': f'https://storage.googleapis.com/write-res/{user.username}/adventure_{adventure.id}/story_{story.id}/cover.jpg'
            })
    
    return render(request, 'main_app/home.html', {'library_items': library_items})

def recent_view(request):
    return render(request, 'main_app/recent.html')

def popular_view(request):
    return render(request, 'main_app/popular.html')

@login_required
def library_view(request):
    source = request.GET.get('source')
    featured_adventure_id = request.GET.get('adventure_id')
    user = request.user
    # Get all adventures with prefetched stories
    base_queryset = Adventure.objects.filter(user=request.user).prefetch_related('stories')
    
    # Handle featured adventure ordering
    if source == 'home' and featured_adventure_id:
        try:
            featured_adventure_id = int(featured_adventure_id)
            featured_adventure = base_queryset.filter(id=featured_adventure_id).first()
            if featured_adventure:
                other_adventures = base_queryset.exclude(id=featured_adventure_id).order_by('-created_at')
                adventures = [featured_adventure] + list(other_adventures)
            else:
                adventures = base_queryset.order_by('-created_at')
        except (ValueError, TypeError):
            adventures = base_queryset.order_by('-created_at')
    else:
        adventures = base_queryset.order_by('-created_at')
    
    adventure_number = len(adventures)
    request.session['adventure_number'] = adventure_number
    library_data = []
    
    for adventure in adventures:
        # Get completed stories for this adventure
        completed_stories = [story for story in adventure.stories.all() if story.status == 'completed']
        
        # Get age group from style data
        style_data = adventure.style_data or {}
        age_group = style_data.get('age_group', 'Not specified')
        
        # Process each completed story
        story_data = []
        for story in completed_stories:
            # Get cover image URL
            
            story_data.append({
                'id': story.id,
                'story_id': story.id,  # Add this to match the template
                'title': story.title,
                'created_at': story.created_at,
                'summary': story.summary,
                'cover_image_url': f'https://storage.googleapis.com/write-res/{user.username}/adventure_{adventure.id}/story_{story.id}/cover.jpg',
                'status': story.status
            })
        
        # Add adventure data with age group
        library_data.append({
            'id': adventure.id,
            'adventure_id': adventure.id,
            'name': adventure.world_data.get('name', ''),
            'created_at': adventure.created_at,
            'updated_at': adventure.updated_at,
            'age_group': age_group,
            'stories': story_data,
            'user_name': user.username
        })
    
    # Get processing stories
    processing_stories = Story.objects.filter(
        adventure__user=request.user,
        status='processing'
    ).select_related('adventure')
    
    context = {
        'library_data': library_data,
        'processing_stories': processing_stories,
        'adventure_number': adventure_number
    }
    
    return render(request, 'main_app/library.html', context)

def message_view(request):
    return HttpResponse("Message functionality will be implemented here.")

def share_view(request):
    return HttpResponse("Sharing functionality will be implemented here.")





@login_required
def start_new_adventure(request):
    """Create a new Adventure instance and redirect to review choices"""
    try:
        adventure = Adventure.objects.create(
            user=request.user,
            adventure_number=Adventure.objects.filter(user=request.user).count() + 1,
            style_data={},
            world_data={},
            character_data=[],
            setting_data=[]
        )
        request.session['adventure_id'] = adventure.id
        return redirect('gemini:review_choices')
    except Exception as e:
        print(f"Error creating new adventure: {str(e)}")
        messages.error(request, "Failed to start new story")
        return redirect('main_app:home')
    
@login_required
@require_http_methods(["POST"])
def generate_audio(request, story_id):
    try:
        story = Story.objects.select_related('content').get(id=story_id)
        adventure_id = story.adventure.id
        data = json.loads(request.body)
        voice_name = data.get('voice', 'en-US-Neural2-J')
        
        # Get the raw content from StoryContent
        try:
            story_content = story.content
            full_text = []
            
            # Iterate through parts in order
            for part_num in range(1, 6):  # Max 5 parts
                part_key = f"Part {part_num}"
                if part_key in story_content.raw_content:
                    full_text.append(f"\n{part_key}\n")
                    part_data = story_content.raw_content[part_key]
                    
                    # Add chapters in order
                    for chapter_num in range(1, 6):  # Max 5 chapters
                        chapter_key = f"Chapter {chapter_num}"
                        if chapter_key in part_data:
                            full_text.append(f"\n{chapter_key}\n")
                            full_text.append(part_data[chapter_key]['full_text'])
            
            raw_text = "\n".join(full_text)
            
            # Start the background task in a thread
            thread = threading.Thread(
                target=synthesize_long_text,
                args=(raw_text, voice_name, story_id, request.user.id, adventure_id)
            )
            thread.daemon = True
            thread.start()
            
            # Return immediately with success status
            return JsonResponse({
                'status': 'success',
                'message': 'Audio generation started in background'
            })
            
        except AttributeError:
            return JsonResponse({
                'status': 'error',
                'message': 'Story content not found'
            }, status=404)

    except Story.DoesNotExist:
        return JsonResponse({
            'status': 'error',
            'message': 'Story not found'
        }, status=404)
    except Exception as e:
        logger.error(f"Error initiating audio generation: {str(e)}", exc_info=True)
        return JsonResponse({
            'status': 'error',
            'message': str(e)
        }, status=500)

@login_required
def check_audio(request, story_id):
    try:
        story = Story.objects.get(id=story_id)
        adventure_id = story.adventure.id
        
        filename = f"{request.user.username}/adventure_{adventure_id}/story_{story_id}/audio.mp3"
        logger.info(f"Checking for audio file: {filename}")

        storage_client = storage.Client()
        bucket = storage_client.bucket('write-res')
        blob = bucket.blob(filename)

        logger.info(f"Checking blob existence for: gs://write-res/{filename}")
        exists = blob.exists()
        logger.info(f"Blob exists: {exists}")

        if exists:
            # Instead of make_public(), construct the public URL directly
            audio_url = f"https://storage.googleapis.com/write-res/{filename}"
            logger.info(f"Audio URL generated: {audio_url}")
            
            return JsonResponse({
                'exists': True,
                'audio_url': audio_url
            })
        
        logger.info("Audio file not found in bucket")
        return JsonResponse({'exists': False})

    except Exception as e:
        logger.error(f"Error in check_audio: {str(e)}", exc_info=True)
        return JsonResponse({
            'status': 'error',
            'message': str(e)
        }, status=500)

@login_required
def story_images(request, story_id):
    """Endpoint to get all images associated with a story."""
    try:
        story = Story.objects.get(id=story_id, adventure__user=request.user)
        images = []
        
        # Get the base GCS URL from settings
        base_url = f'https://storage.googleapis.com/write-res/{request.user.id}/adventure_{story.adventure.id}/story_{story.id}/story_images/'
        
        # Add cover image if it exists
        cover_image_url = base_url + f'cover.jpg'
        images.append({
            'url': cover_image_url,
            'thumbnail_url': cover_image_url,  # You could create actual thumbnails in the future
            'type': 'cover'
        })
        
        # Get chapter images if they exist
        if hasattr(story, 'story_images'):
            chapter_images = story.story_images.chapter_images.all()
            for chapter_image in chapter_images:
                image_url = chapter_image.image.url
                images.append({
                    'url': image_url,
                    'thumbnail_url': image_url,  # You could create actual thumbnails in the future
                    'type': 'chapter',
                    'chapter_number': chapter_image.chapter_number,
                    'text_marker': chapter_image.text_marker
                })
        
        return JsonResponse({
            'status': 'success',
            'images': images
        })
        
    except Story.DoesNotExist:
        return JsonResponse({
            'status': 'error',
            'message': 'Story not found'
        }, status=404)
    except Exception as e:
        logger.error(f"Error fetching story images: {str(e)}")
        return JsonResponse({
            'status': 'error',
            'message': 'Error fetching images'
        }, status=500)

@login_required
def check_story_file(request, story_id):
    try:
        story = Story.objects.get(id=story_id)
        adventure_id = story.adventure.id
        
        filename = f"{request.user.username}/adventure_{adventure_id}/story_{story_id}/final.pdf"
        logger.info(f"Checking for PDF file: {filename}")

        storage_client = storage.Client()
        bucket = storage_client.bucket('write-res')
        blob = bucket.blob(filename)

        logger.info(f"Checking blob existence for: gs://write-res/{filename}")
        exists = blob.exists()
        logger.info(f"Blob exists: {exists}")

        if exists:
            # Construct the public URL for the PDF file
            story_url = f"https://storage.googleapis.com/write-res/{filename}"
            logger.info(f"PDF URL generated: {story_url}")
            
            return JsonResponse({
                'exists': True,
                'story_url': story_url
            })
        
        logger.info("PDF file not found in bucket")
        return JsonResponse({'exists': False})
        
    except Story.DoesNotExist:
        return JsonResponse({
            'status': 'error',
            'message': 'Story not found'
        }, status=404)
    except Exception as e:
        logger.error(f"Error checking PDF file: {str(e)}", exc_info=True)
        return JsonResponse({
            'status': 'error',
            'message': str(e)
        }, status=500)
    
@login_required
def check_image_in_bucket(bucket, image_path):
    blob = bucket.blob(image_path)
    exists = blob.exists()
    logger.info(f"Image {image_path} exists in bucket: {exists}")
    return exists

def center_text_on_page(canvas, doc, text, style):
    canvas.saveState()
    text_obj = Paragraph(text, style)
    width, height = text_obj.wrapOn(canvas, letter[0], letter[1])
    x = (letter[0] - width) / 2
    y = (letter[1] - height) / 2
    text_obj.drawOn(canvas, x, y)
    canvas.restoreState()

@login_required
def create_final_story(request, story_id):
    try:
        # Get story with related content and images
        story = Story.objects.select_related(
            'content',
            'story_images'
        ).prefetch_related(
            'story_images__chapter_images'
        ).get(id=story_id)
        
        adventure_id = story.adventure.id
        user_name = request.user.username

        # Create a temporary directory to store images
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create the nested directory structure for the PDF
            pdf_dir = os.path.join(temp_dir, user_name, f"adventure_{adventure_id}", f"story_{story_id}")
            os.makedirs(pdf_dir, exist_ok=True)
            
            # Prepare text data and download images
            text_data = {}
            image_paths = {}
            styles = getSampleStyleSheet()
            paragraph_style = ParagraphStyle(
                name = 'chapter_text',
                fontSize = 16,
                leftIndent = 24,
                spaceAfter = 14,
                leading = 21
            )
            story_elements = []  # Initialize story_elements here
            
            try:
                story_content = story.content.raw_content
                # Organize text data and download images
                for part_key, part_data in story_content.items():
                    for chapter_key, chapter_data in part_data.items():
                        part_chapter = (part_key, chapter_key)
                        text_data[part_chapter] = chapter_data['full_text']
                        
                        # Extract numbers from part_key and chapter_key
                        part_num = part_key.split()[-1]  # Gets the number from "Part X"
                        chapter_num = chapter_key.split()[-1]  # Gets the number from "Chapter X"
                        
                        # Construct the image URL directly
                        image_url = f"https://storage.googleapis.com/write-res/{user_name}/adventure_{adventure_id}/story_{story_id}/Part{part_num}_Chapter{chapter_num}.jpg"
                        # Use a simpler temporary filename, matching cover image pattern
                        image_path = os.path.join(temp_dir, f"chapter_{part_num}_{chapter_num}.jpg")
                        
                        try:
                            logger.info(f"Attempting to download image from: {image_url}")
                            urlretrieve(image_url, image_path)
                            
                            if os.path.exists(image_path):
                                file_size = os.path.getsize(image_path)
                                logger.info(f"Downloaded image size: {file_size} bytes")
                                if file_size > 0:
                                    # Store the full path in image_paths
                                    image_paths[part_chapter] = image_path
                                    logger.info(f"Successfully downloaded image to {image_path}")
                        except Exception as e:
                            logger.warning(f"Could not download image {image_url}: {str(e)}")

                # Handle cover image
                cover_url = f"https://storage.googleapis.com/write-res/{user_name}/adventure_{adventure_id}/story_{story_id}/cover.jpg"
                cover_path = os.path.join(temp_dir, "cover.jpg")
                try:
                    logger.info(f"Attempting to download cover from: {cover_url}")
                    urlretrieve(cover_url, cover_path)
                    
                    if os.path.exists(cover_path) and os.path.getsize(cover_path) > 0:
                        if cover_img := verify_and_get_image(cover_path):
                            logger.info("Successfully added cover image to PDF")
                            story_elements.append(Paragraph(f"<h1>{story.title}</h1>", styles['Title']))
                            story_elements.append(Spacer(1, 2 * inch))
                            story_elements.append(cover_img)
                except Exception as e:
                    logger.warning(f"Could not download cover image: {str(e)}")

                # Set up the PDF path
                pdf_filename = f"{user_name}/adventure_{adventure_id}/story_{story_id}/final.pdf"
                pdf_path = os.path.join(pdf_dir, "final.pdf")
                
                # Generate PDF
                #doc = SimpleDocTemplate(pdf_path, pagesize=(8.5 * inch, 11 * inch))
                doc = SimpleDocTemplate(
                    pdf_path,
                    pagesize=(8.5 * inch, 11 * inch),
                    leftMargin=1 * inch,
                    rightMargin=1 * inch,
                    topMargin=1 * inch,
                    bottomMargin=1 * inch
                )
                #styles = getSampleStyleSheet()

                # Add title page if not already added with cover
                if not story_elements:
                    title = Paragraph(f"<h1>{story.title}</h1>", styles['Title'])
                    story_elements.append(title)
                    story_elements.append(PageBreak())

                # Add chapters with images
                sorted_chapters = sorted(text_data.keys())
                for part_chapter in sorted_chapters:
                    part_name, chapter_name = part_chapter
                    text = text_data[part_chapter]
                    image_path = image_paths.get(part_chapter)

                    # Add PageBreak before each chapter
                    story_elements.append(PageBreak())

                    # If this is Chapter 1 of any part, add the part title first
                    if "Chapter 1" in chapter_name:
                        story_elements.append(Paragraph(f"<h1>{part_name}</h1>", styles['Title']))
                        story_elements.append(PageBreak())

                    # Then add the chapter heading and image
                    if image_path and os.path.exists(image_path):
                        try:
                            if chapter_img := verify_and_get_image(image_path):
                                logger.info(f"Successfully added chapter image to PDF: {image_path}")
                                story_elements.append(chapter_img)
                                story_elements.append(PageBreak())
                                
                                logger.info("Chapter image added to story_elements")
                        except Exception as e:
                            logger.error(f"Error adding chapter image to PDF: {str(e)}")

                    # Finally add the chapter text
                    text_paragraph = Paragraph(text, paragraph_style)
                    story_elements.append(Paragraph(f"<h1>{chapter_name}</h1>", styles['Title']))
                    story_elements.append(Spacer(1, 0.5 * inch))
                    story_elements.append(text_paragraph)
                    story_elements.append(Spacer(1, 0.5 * inch))

                # Build the PDF with additional settings
                doc.build(story_elements, onFirstPage=lambda canvas, doc: canvas.setPageSize((8.5*inch, 11*inch)))

                # Initialize storage client for PDF upload
                storage_client = storage.Client()
                bucket = storage_client.bucket('write-res')
                blob = bucket.blob(pdf_filename)
                
                with open(pdf_path, 'rb') as pdf_file:
                    blob.upload_from_file(
                        pdf_file, 
                        content_type='application/pdf',
                    )

                return JsonResponse({
                    'status': 'success',
                    'message': 'PDF generated and uploaded successfully',
                    'filename': pdf_filename
                })

            except AttributeError as e:
                logger.error(f"Content or image data missing: {e}")
                return JsonResponse({
                    'status': 'error',
                    'message': 'Required content missing'
                }, status=404)

    except Story.DoesNotExist:
        return JsonResponse({
            'status': 'error',
            'message': 'Story not found'
        }, status=404)
    except Exception as e:
        logger.error(f"Error in create_final_story: {str(e)}", exc_info=True)
        return JsonResponse({
            'status': 'error',
            'message': str(e)
        }, status=500)
    
@login_required
def get_story_content(request, story_id):
    try:
        story = Story.objects.select_related('content').get(id=story_id)
        
        # Combine all full_text content from raw_content
        combined_text = ""
        raw_content = story.content.raw_content
        
        # Sort parts and chapters to maintain order
        for part_key in sorted(raw_content.keys()):
            part = raw_content[part_key]
            for chapter_key in sorted(part.keys()):
                chapter = part[chapter_key]
                combined_text += chapter['full_text'] + "\n\n"
        
        return JsonResponse({
            'status': 'success',
            'content': combined_text.strip()
        })
    except Story.DoesNotExist:
        return JsonResponse({
            'status': 'error',
            'message': 'Story not found'
        }, status=404)
    except Exception as e:
        return JsonResponse({
            'status': 'error',
            'message': str(e)
        }, status=500)

@login_required
@require_http_methods(["POST"])
def update_story_content(request, story_id):
    try:
        data = json.loads(request.body)
        content = data.get('content', '').strip()
        
        story = Story.objects.select_related('content').get(id=story_id)
        
        # Split content into parts and chapters
        paragraphs = [p for p in content.split('\n\n') if p.strip()]
        
        # Reconstruct the raw_content structure
        raw_content = {}
        current_part = 1
        current_chapter = 1
        chapters_per_part = 3  # Adjust based on your structure
        
        for i, text in enumerate(paragraphs):
            part_num = f"part{(i // chapters_per_part) + 1}"
            chapter_num = f"chapter{(i % chapters_per_part) + 1}"
            
            if part_num not in raw_content:
                raw_content[part_num] = {}
            
            raw_content[part_num][chapter_num] = {
                'full_text': text,
                'summary': story.content.raw_content.get(part_num, {}).get(chapter_num, {}).get('summary', '')
            }
        
        # Update the content
        story.content.raw_content = raw_content
        story.content.save()
        
        # Check if PDF exists and delete it
        storage_client = storage.Client()
        bucket = storage_client.bucket('write-res')
        pdf_blob_name = f"{request.user.id}/adventure_{story.adventure_id}/story_{story_id}/edited.pdf"
        blob = bucket.blob(pdf_blob_name)
        
        if blob.exists():
            blob.delete()
        
        return JsonResponse({'status': 'success'})
    
    except Story.DoesNotExist:
        return JsonResponse({
            'status': 'error',
            'message': 'Story not found'
        }, status=404)
    except Exception as e:
        return JsonResponse({
            'status': 'error',
            'message': str(e)
        }, status=500)

def verify_and_get_image(image_path):
    try:
        logger.info(f"Starting image verification for: {image_path}")
        # First verify with PIL
        with PILImage.open(image_path) as pil_img:
            pil_img.verify()
            logger.info("PIL verification passed")
            # Get image dimensions
            with PILImage.open(image_path) as pil_img:
                img_width, img_height = pil_img.size
                logger.info(f"Image dimensions: {img_width}x{img_height}")
        
        # Calculate proportional dimensions
        img_width = (8.5 * inch) * 0.7
        img_height = (11 * inch) * 0.7

        # Just pass the file path directly to Image
        img = Image(image_path, width=img_width, height=img_height)
        logger.info(f"Image object created: {img}")
        
        return img
    except Exception as e:
        logger.error(f"Image verification failed: {str(e)}")
        return None

    