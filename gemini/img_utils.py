import os
from google import  genai
from google.genai import types
from PIL import Image, ImageDraw, ImageFont
from io import BytesIO
from google.cloud import secretmanager
import logging
from google.cloud import storage
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import StoryImages, Adventure

logger = logging.getLogger(__name__)
def get_secret(secret_id):
    try:
        project_id = os.environ.get('GOOGLE_CLOUD_PROJECT')
        if not project_id:
            raise ValueError("GOOGLE_CLOUD_PROJECT environment variable is not set")
        client = secretmanager.SecretManagerServiceClient()
        name = f"projects/{project_id}/secrets/{secret_id}/versions/latest"
        response = client.access_secret_version(request={"name": name})
        return response.payload.data.decode("UTF-8")
    except Exception as e:
        print(f"Error accessing secret {secret_id}: {str(e)}")
        return None
GOOGLE_API_KEY = get_secret('GOOGLE_API_KEY')
if not GOOGLE_API_KEY:
    raise ValueError("GOOGLE_API_KEY environment variable must be set")


def generate_image(prompt):
    try:
        logger.info(f"Starting image generation with prompt: {prompt}")
        
        client = genai.Client(api_key=GOOGLE_API_KEY)
        
        config = types.GenerateImagesConfig(
            number_of_images=1,
            include_rai_reason=True,
            output_mime_type='image/jpeg'
        )

        response = client.models.generate_images(
            model='imagen-3.0-generate-002',
            prompt=prompt,
            config=config
        )

        if hasattr(response, 'generated_images'):
            for generated_image in response.generated_images:
                if hasattr(generated_image, 'image') and hasattr(generated_image.image, 'image_bytes'):
                    try:
                        image_bytes = generated_image.image.image_bytes
                        if not image_bytes:
                            logger.error("Received empty image bytes")
                            return None
                            
                        logger.debug(f"Received image bytes of length: {len(image_bytes)}")
                        
                        # Create BytesIO object and write bytes
                        image_io = BytesIO(image_bytes)
                        
                        # Try to open and verify the image
                        image = Image.open(image_io)
                        image.verify()  # Verify it's a valid image
                        image_io.seek(0)  # Reset after verify
                        image = Image.open(image_io)  # Reopen for actual use
                        
                        logger.info("Successfully created image")
                        return image
                    except Exception as e:
                        logger.error(f"Error processing image bytes: {str(e)}")
                        return None
                else:
                    logger.error("Response missing image or image_bytes attribute")
        else:
            logger.error("Response missing generated_images attribute")
            
        return None

    except Exception as e:
        logger.error(f"Error in generate_image: {str(e)}", exc_info=True)
        return None


def manipulate_image(image_path, output_path, new_width, new_height, top_text, bottom_text, font_size=30, font_color=(255, 255, 255), text_bg_color=(0, 0, 0, 128)):
    """
    Resizes an image and overlays text at the top and bottom.

    Args:
        image_path (str): Path to the input image.
        output_path (str): Path to save the modified image.
        new_width (int): Desired width of the output image.
        new_height (int): Desired height of the output image.
        top_text (str): Text to overlay at the top.
        bottom_text (str): Text to overlay at the bottom.
        font_size (int): Size of the font for the text.
        font_color (tuple): RGB color tuple for the text (default is white).
        text_bg_color (tuple): RGBA color tuple for the text background (default is semi-transparent black).
    """
    try:
        # Open the image
        img = Image.open(image_path).convert("RGBA")

        # Resize the image
        resized_img = img.resize((new_width, new_height))
        draw = ImageDraw.Draw(resized_img)
        img_width, img_height = resized_img.size

        # Choose a font (you might need to adjust the path based on your system)
        try:
            font = ImageFont.truetype("arial.ttf", font_size)
        except IOError:
            font = ImageFont.load_default()
            print("Arial font not found, using default font.")

        # --- Overlay Top Text ---
        top_text_width, top_text_height = draw.textbbox((0, 0), top_text, font=font)[2:]
        top_text_x = (img_width - top_text_width) // 2
        top_text_y = 10  # Adjust vertical position as needed

        # Draw background rectangle for top text
        padding = 5
        draw.rectangle(
            (top_text_x - padding, top_text_y - padding, top_text_x + top_text_width + padding, top_text_y + top_text_height + padding),
            fill=text_bg_color
        )

        # Draw top text
        draw.text((top_text_x, top_text_y), top_text, font=font, fill=font_color)

        # --- Overlay Bottom Text ---
        bottom_text_width, bottom_text_height = draw.textbbox((0, 0), bottom_text, font=font)[2:]
        bottom_text_x = (img_width - bottom_text_width) // 2
        bottom_text_y = img_height - bottom_text_height - 10  # Adjust vertical position as needed

        # Draw background rectangle for bottom text
        draw.rectangle(
            (bottom_text_x - padding, bottom_text_y - padding, bottom_text_x + bottom_text_width + padding, bottom_text_y + bottom_text_height + padding),
            fill=text_bg_color
        )

        # Draw bottom text
        draw.text((bottom_text_x, bottom_text_y), bottom_text, font=font, fill=font_color)

        # Save the modified image
        resized_img.save(output_path)
        print(f"Image processed and saved to {output_path}")

    except FileNotFoundError:
        print(f"Error: Image not found at {image_path}")
    except Exception as e:
        print(f"An error occurred: {e}")

def generate_and_store_image(story_instance, prompt, part_key=None, chapter_key=None):
    """
    Generate an image based on a prompt and store it in GCS.
    
    Args:
        story_instance (Story): The Story model instance
        prompt (str): The prompt for image generation
        part_key (str): The part identifier (e.g., 'part_1', 'part_2')
        chapter_key (str): The chapter identifier (e.g., 'chapter_1', 'chapter_2')
    
    Returns:
        bool: Whether the operation was successful
    """
    try:
        logger.debug(f"Generating image for story {story_instance.id} with prompt: {prompt}")
        generated_image = generate_image(prompt)
        
        if not generated_image:
            logger.error("Image generation returned None")
            return False
            
        # Create StoryImages instance if it doesn't exist
        story_images, created = StoryImages.objects.get_or_create(story=story_instance)
        
        # Convert PIL Image to bytes
        image_io = BytesIO()
        generated_image.save(image_io, format='JPEG')
        image_io.seek(0)
        
        # Generate filename based on part and chapter
        if part_key and chapter_key:
            # Extract just the numbers, handling "Part X" and "Chapter Y" format
            part_num = part_key.replace('Part ', '').strip()
            chapter_num = chapter_key.replace('Chapter ', '').strip()
            filename = f"Part{part_num}_Chapter{chapter_num}.jpg"
        else:
            filename = "cover.jpg"
        
        # Save to Google Cloud Storage
        username = story_instance.adventure.user.username
        adventure_id = story_instance.adventure.id
        storage_client = storage.Client()
        bucket = storage_client.bucket('write-res')
        blob = bucket.blob(f"{username}/adventure_{adventure_id}/story_{story_instance.id}/{filename}")
        
        # Upload the image
        blob.upload_from_file(
            image_io,
            content_type='image/jpeg'
        )
        
        logger.debug(f"Image saved to GCS for story {story_instance.id} as {filename}")
        return True

    except Exception as e:
        logger.error(f"Error in generate_and_store_image: {str(e)}")
        return False

def get_stored_image(story_instance, part_key=None, chapter_key=None):
    """
    Retrieve an image from GCS for manipulation.
    
    Args:
        story_instance (Story): The Story model instance
        part_key (str): The part identifier (e.g., 'part_1', 'part_2')
        chapter_key (str): The chapter identifier (e.g., 'chapter_1', 'chapter_2')
    
    Returns:
        PIL.Image or None: The image if successfully retrieved, None if any error occurs
    """
    try:
        # Generate filename based on part and chapter
        if part_key and chapter_key:
            filename = f"Part{part_key}_Chapter{chapter_key}.jpg"
        else:
            filename = "cover.jpg"

        username = story_instance.adventure.user.username
        adventure_id = story_instance.adventure.id
        storage_client = storage.Client()
        bucket = storage_client.bucket('write-res')
        blob = bucket.blob(f"{username}/adventure_{adventure_id}/story_{story_instance.id}/{filename}")
        
        if not blob.exists():
            logger.error(f"Image not found in GCS for story {story_instance.id}, filename {filename}")
            return None
            
        # Download to memory for manipulation
        image_data = BytesIO()
        blob.download_to_file(image_data)
        image_data.seek(0)
        return Image.open(image_data)
        
    except Exception as e:
        logger.error(f"Error retrieving image from GCS: {str(e)}")
        return None

def add_image_data(story_instance, part_key=None, chapter_key=None):
    """
    Add text overlays to any story image, with specific handling for cover images.
    """
    try:
        # Extract user name from the story instance
        user_name = story_instance.adventure.user.username
        adventure_id = story_instance.adventure.id
        story_id = story_instance.id

        # Construct image path based on whether it's a cover or chapter image
        if part_key and chapter_key:
            # Extract numbers from part_key and chapter_key
            part_num = part_key.split()[-1]  # Gets the number from "Part X"
            chapter_num = chapter_key.split()[-1]  # Gets the number from "Chapter X"
            image_path = f"{user_name}/adventure_{adventure_id}/story_{story_id}/Part{part_num}_Chapter{chapter_num}.jpg"
        else:
            # Cover image path
            image_path = f"{user_name}/adventure_{adventure_id}/story_{story_id}/cover.jpg"

        # Get the image using new naming convention
        image = get_stored_image(story_instance, part_key, chapter_key)
        if not image:
            logger.error(f"Failed to retrieve image for story {story_id} at path {image_path}")
            return False

        # Set dimensions with 2:3 ratio
        target_width = 800  # You can adjust this base width as needed
        target_height = int(target_width * 1.3)  
        
        # Resize image maintaining aspect ratio and adding padding if needed
        current_ratio = image.size[0] / image.size[1]
        target_ratio = target_width / target_height
        
        if current_ratio > target_ratio:
            # Image is too wide
            new_height = target_height
            new_width = int(new_height * current_ratio)
        else:
            # Image is too tall
            new_width = target_width
            new_height = int(new_width / current_ratio)
            
        image = image.resize((new_width, new_height), Image.Resampling.LANCZOS)
        
        # Create new image with padding to achieve exact 2:3 ratio
        new_image = Image.new('RGB', (target_width, target_height), 'black')
        paste_x = (target_width - new_width) // 2
        paste_y = (target_height - new_height) // 2
        new_image.paste(image, (paste_x, paste_y))
        image = new_image

        if not part_key and chapter_key:
            # Prepare for text overlay
            draw = ImageDraw.Draw(image)
            
            # Calculate font sizes based on image dimensions
            title_font_size = int(target_width * 0.1)  # 10% of image width
            author_font_size = int(title_font_size * 0.6)  # 60% of title font size

            # Try to load fonts with calculated sizes
            try:
                # Try system fonts in order of preference
                font_paths = [
                    "arial.ttf",
                    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",  # Common on Linux
                    "/System/Library/Fonts/Helvetica.ttc",  # Common on macOS
                    "C:\\Windows\\Fonts\\arial.ttf"  # Common on Windows
                ]
                
                title_font = None
                for font_path in font_paths:
                    try:
                        title_font = ImageFont.truetype(font_path, size=title_font_size)
                        author_font = ImageFont.truetype(font_path, size=author_font_size)
                        break
                    except IOError:
                        continue
                
                if not title_font:
                    raise IOError("No suitable font found")
                    
            except IOError:
                print("No suitable fonts found, using default font")
                title_font = ImageFont.load_default()
                author_font = ImageFont.load_default()

            # Get story title and handle long titles
            title = story_instance.title or f"Story #{story_instance.id}"
            
            # Get user name
            try:
                user_name = story_instance.adventure.user.userprofile.name
            except (AttributeError, Adventure.user.RelatedObjectDoesNotExist):
                try:
                    user_name = story_instance.adventure.user.username
                except AttributeError:
                    user_name = "Anonymous"
            author_text = f"By {user_name}"

            # Function to wrap text
            def wrap_text(text, font, max_width):
                words = text.split()
                lines = []
                current_line = []
                
                for word in words:
                    current_line.append(word)
                    line = ' '.join(current_line)
                    bbox = draw.textbbox((0, 0), line, font=font)
                    if bbox[2] - bbox[0] > max_width:
                        if len(current_line) == 1:
                            lines.append(line)
                            current_line = []
                        else:
                            current_line.pop()
                            lines.append(' '.join(current_line))
                            current_line = [word]
                
                if current_line:
                    lines.append(' '.join(current_line))
                return lines

            # Calculate maximum width for text (80% of image width)
            max_text_width = int(target_width * 0.8)
            
            # Wrap title if needed
            title_lines = wrap_text(title, title_font, max_text_width)
            
            # Calculate total height needed for title
            line_spacing = title_font_size * 0.2  # 20% of font size
            total_title_height = (title_font_size + line_spacing) * len(title_lines)
            
            # Draw title lines
            y_position = 50  # Starting position from top
            for line in title_lines:
                bbox = draw.textbbox((0, 0), line, font=title_font)
                text_width = bbox[2] - bbox[0]
                x_position = (target_width - text_width) // 2
                draw.text((x_position, y_position), line, fill='black', font=title_font)
                y_position += title_font_size + line_spacing

            # Draw author name at bottom
            author_bbox = draw.textbbox((0, 0), author_text, font=author_font)
            author_width = author_bbox[2] - author_bbox[0]
            author_x = (target_width - author_width) // 2
            author_y = target_height - author_font_size - 50  # 50 pixels from bottom
            draw.text((author_x, author_y), author_text, fill='black', font=author_font)

        # Generate filename for saving
        if part_key and chapter_key:
            filename = f"Part{part_key}_Chapter{chapter_key}.jpg"
        else:
            filename = "cover.jpg"

        # Save back to GCS
        image_io = BytesIO()
        image.save(image_io, format='JPEG', quality=95)
        image_io.seek(0)
        
        storage_client = storage.Client()
        bucket = storage_client.bucket('write-res')
        blob = bucket.blob(f"{user_name}/adventure_{adventure_id}/story_{story_id}/{filename}")
        blob.upload_from_file(
            image_io,
            content_type='image/jpeg'
        )

        return True

    except Exception as e:
        logger.error(f"Error in add_image_data: {str(e)}")
        return False

