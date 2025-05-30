import os
import json
import time
import random
import logging
from google.cloud import storage
import google.generativeai as genai
from gemini.models import Adventure, StoryContent
from google.cloud import secretmanager
from .img_utils import generate_and_store_image, add_image_data

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Create your tests here.

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

def get_bucket_data(bucket_name, blob_name):
    try:
        storage_client = storage.Client()
        bucket = storage_client.bucket(bucket_name)
        blob = bucket.blob(blob_name)
        system_data = blob.download_as_text()
        return system_data
    except Exception as e:
        logger.error(f"Error fetching system instructions: {e}")
        raise

def get_response(prompt, chat):
    """Gets a response from the model using chat."""
    try:
        logger.info(f"Making Google AI request with prompt length: {len(prompt)}")
        start_time = time.time()

        # Break long prompts into chunks if needed
        if len(prompt) > 100000:
            logger.debug("Breaking long prompt into chunks")
            chunks = chunk_context(prompt)
            final_response = ""
            for i, chunk in enumerate(chunks):
                if i < len(chunks) - 1:
                    # For all but the last chunk, just acknowledge receipt
                    chat.send_message(chunk)
                else:
                    # For the last chunk, get the actual response
                    response = chat.send_message(chunk)
                    prompt_token_count = response.usage_metadata.prompt_token_count
                    candidates_token_count = response.usage_metadata.candidates_token_count
                    final_response = response.text
        else:
            response = chat.send_message(prompt)
            prompt_token_count = response.usage_metadata.prompt_token_count
            candidates_token_count = response.usage_metadata.candidates_token_count
            final_response = response.text
        
        duration = time.time() - start_time
        logger.info(f"Google AI request completed in {duration:.2f} seconds")
        
        return final_response, prompt_token_count, candidates_token_count
        
    except Exception as e:
        logger.error(f"Google AI request failed: {str(e)}")
        logger.error(f"Request details - Prompt length: {len(prompt)}")
        raise


def create_cache(cache_data):
    try:
        logger.debug("Starting cache creation process...")
        
        # Configure the model
        genai.configure(api_key=GOOGLE_API_KEY)
        
        # Create model without storing large context
        model = genai.GenerativeModel(
            model_name='gemini-1.5-pro',
            generation_config={
                'temperature': 0.7,
                'top_p': 0.8,
                'top_k': 40,
                'max_output_tokens': 2048,  # Reduced from 2048
            }
        )
        
        # Start chat with minimal context
        chat = model.start_chat()
        
        # Send initial context in chunks if needed
        context_chunks = chunk_context(cache_data)
        for chunk in context_chunks:
            response = chat.send_message(
                f"Here is part of the story context: {chunk}",
                generation_config={'temperature': 0.1}  # Low temperature for context processing
            )
            prompt_token_count = response.usage_metadata.prompt_token_count
            candidates_token_count = response.usage_metadata.candidates_token_count
        
        return chat, prompt_token_count, candidates_token_count

    except Exception as e:
        logger.error(f"Context creation failed: {str(e)}", exc_info=True)
        raise

def chunk_context(context_data, chunk_size=2000):
    """Split context into manageable chunks."""
    try:
        if isinstance(context_data, str):
            # Split by newlines first to keep logical blocks together
            parts = context_data.split('\n')
            chunks = []
            current_chunk = []
            current_length = 0
            
            for part in parts:
                if current_length + len(part) > chunk_size:
                    chunks.append('\n'.join(current_chunk))
                    current_chunk = [part]
                    current_length = len(part)
                else:
                    current_chunk.append(part)
                    current_length += len(part)
            
            if current_chunk:
                chunks.append('\n'.join(current_chunk))
            
            return chunks
        else:
            # If it's not a string (e.g., dict), convert to string first
            return chunk_context(json.dumps(context_data))
    except Exception as e:
        logger.error(f"Error chunking context: {str(e)}")
        raise

def remove_null_recursive(data):
    """Recursively removes null values from a dictionary."""
    if isinstance(data, dict):
        return {k: remove_null_recursive(v) for k, v in data.items() if v is not None}
    elif isinstance(data, list):
        return [remove_null_recursive(item) for item in data if item is not None]
    return data

def stringify_json(data):
    data = json.dumps(data) 
    data = data.strip('{}"')
    data = data + '\n'
    return data

def prepare_adventure_data(adventure_id):
    """Formats the cache data for the story generation."""
    try:
        # Get only essential data
        adventure = Adventure.objects.get(id=adventure_id)
        adventure_not_null = remove_null_recursive(adventure)
        essential_data = {
            'style': stringify_json(adventure_not_null.style_data),
            'world': stringify_json(adventure_not_null.world_data),
            'characters': stringify_json(adventure_not_null.character_data),
            'settings': stringify_json(adventure_not_null.setting_data)
        }
        data = json.dumps(essential_data)
        try: 
            age_group = adventure.style_data.get('age_group', '')
            if age_group == None:
                age_group = '7 through 11'
        except:
            age_group = '7 through 11'
        return data, age_group
    except Exception as e:
        logger.error(f"Error formatting cache data: {str(e)}")
        raise

def set_outline_format(age_group):
    if age_group == '3 through 6':
        outline_format = {
                "title": "title",
                "Part 1": {
                    "Chapter 1": "chapter_summary", 
                    "Chapter 2": "chapter_summary", 
                    "Chapter 3": "chapter_summary" 
                    },
                "Part 2": {
                    "Chapter 1": "chapter_summary", 
                    "Chapter 2": "chapter_summary", 
                    "Chapter 3": "chapter_summary" 
                }
            }
    elif age_group == '5 through 8':
        outline_format = {
                "title": "title", 
                "Part 1": {
                    "Chapter 1": "chapter_summary", 
                    "Chapter 2": "chapter_summary", 
                    "Chapter 3": "chapter_summary", 
                    "Chapter 4": "chapter_summary",
                    "Chapter 5": "chapter_summary"
                    }, 
                "Part 2": {
                    "Chapter 1": "chapter_summary", 
                    "Chapter 2": "chapter_summary", 
                    "Chapter 3": "chapter_summary", 
                    "Chapter 4": "chapter_summary",
                    "Chapter 5": "chapter_summary"
                    }
            }
    elif age_group == '7 through 11':
        outline_format = {
                "title": "title", 
                "Part 1": {
                    "Chapter 1": "chapter_summary", 
                    "Chapter 2": "chapter_summary", 
                    "Chapter 3": "chapter_summary", 
                    "Chapter 4": "chapter_summary",
                    "Chapter 5": "chapter_summary"
                    }, 
                "Part 2": {
                    "Chapter 1": "chapter_summary", 
                    "Chapter 2": "chapter_summary", 
                    "Chapter 3": "chapter_summary", 
                    "Chapter 4": "chapter_summary",
                    "Chapter 5": "chapter_summary"
                    }, 
                "Part 3": {
                    "Chapter 1": "chapter_summary", 
                    "Chapter 2": "chapter_summary", 
                    "Chapter 3": "chapter_summary", 
                    "Chapter 4": "chapter_summary",
                    "Chapter 5": "chapter_summary"
                }
            }
    elif age_group == '10 through 13':
        outline_format = {
                "title": "title", 
                "Part 1": {
                    "Chapter 1": "chapter_summary", 
                    "Chapter 2": "chapter_summary", 
                    "Chapter 3": "chapter_summary", 
                    "Chapter 4": "chapter_summary",
                    "Chapter 5": "chapter_summary"
                    }, 
                "Part 2": {
                    "Chapter 1": "chapter_summary", 
                    "Chapter 2": "chapter_summary", 
                    "Chapter 3": "chapter_summary", 
                    "Chapter 4": "chapter_summary",
                    "Chapter 5": "chapter_summary"
                    }, 
                "Part 3": {
                    "Chapter 1": "chapter_summary", 
                    "Chapter 2": "chapter_summary", 
                    "Chapter 3": "chapter_summary", 
                    "Chapter 4": "chapter_summary",
                    "Chapter 5": "chapter_summary"
                },
                "Part 4": {
                    "Chapter 1": "chapter_summary", 
                    "Chapter 2": "chapter_summary", 
                    "Chapter 3": "chapter_summary", 
                    "Chapter 4": "chapter_summary",
                    "Chapter 5": "chapter_summary"
                }
            }
    else:
        outline_format = {
                "title": "title", 
                "Part 1": {
                    "Chapter 1": "chapter_summary", 
                    "Chapter 2": "chapter_summary", 
                    "Chapter 3": "chapter_summary", 
                    "Chapter 4": "chapter_summary",
                    "Chapter 5": "chapter_summary"
                    }, 
                "Part 2": {
                    "Chapter 1": "chapter_summary", 
                    "Chapter 2": "chapter_summary", 
                    "Chapter 3": "chapter_summary", 
                    "Chapter 4": "chapter_summary",
                    "Chapter 5": "chapter_summary"
                    }, 
                "Part 3": {
                    "Chapter 1": "chapter_summary", 
                    "Chapter 2": "chapter_summary", 
                    "Chapter 3": "chapter_summary", 
                    "Chapter 4": "chapter_summary",
                    "Chapter 5": "chapter_summary"
                },
                "Part 4": {
                    "Chapter 1": "chapter_summary", 
                    "Chapter 2": "chapter_summary", 
                    "Chapter 3": "chapter_summary", 
                    "Chapter 4": "chapter_summary",
                    "Chapter 5": "chapter_summary"
                },
                "Part 5": {
                    "Chapter 1": "chapter_summary", 
                    "Chapter 2": "chapter_summary", 
                    "Chapter 3": "chapter_summary", 
                    "Chapter 4": "chapter_summary",
                    "Chapter 5": "chapter_summary"
                }
            }
    return outline_format

def fix_outline_format(incorrect_outline, age_group):
    """
    Sends a one-off request to Gemini to fix an incorrectly formatted outline.
    
    Args:
        incorrect_outline (dict/str): The incorrectly formatted outline
        age_group (str): The age group to determine correct format
    
    Returns:
        dict: The corrected outline
    """
    try:
        # Get the expected structure
        expected_structure = set_outline_format(age_group)
        
        # Create a new model instance for this one-off request
        model = genai.GenerativeModel(
            model_name='gemini-1.5-pro',
            generation_config={
                'temperature': 0.1,  # Low temperature for more structured candidates
                'top_p': 0.8,
                'top_k': 40,
            }
        )

        # Format the prompt
        format_prompt = f"""
        Please reformat the following story outline to match the required structure exactly.

        Required structure format:
        {json.dumps(expected_structure, indent=2)}

        Current incorrect outline:
        {json.dumps(incorrect_outline, indent=2)}

        Please provide ONLY the reformatted outline as valid JSON with no additional text or explanation.
        Preserve the story content but make it fit the required structure.
        """

        # Get the response
        response = model.generate_content(format_prompt)
        
        # Parse the response
        try:
            # Clean up the response text
            fixed_outline_text = response.text.strip()
            if fixed_outline_text.startswith('```json'):
                fixed_outline_text = fixed_outline_text.replace('```json', '').replace('```', '').strip()
            
            # Parse as JSON
            fixed_outline = json.loads(fixed_outline_text)
            
            # Validate the fixed outline
            is_valid, error_msg = validate_outline_structure(fixed_outline, age_group)
            if is_valid:
                return fixed_outline
            else:
                raise ValueError(f"Fixed outline still invalid: {error_msg}")
                
        except json.JSONDecodeError as e:
            raise ValueError(f"Failed to parse fixed outline as JSON: {str(e)}")
            
    except Exception as e:
        logger.error(f"Error fixing outline format: {str(e)}")
        raise

def get_outline(prompt, chat, age_group, story_instance):
    """Generates a story outline and validates its structure."""
    # Get the expected format
    expected_format = set_outline_format(age_group)
    format_example = str(expected_format)
    
    outline_prompt = f"""
    Create an outline for a story about: {prompt}

    The outline MUST follow this exact JSON structure:
    {format_example}

    Each string should be a descriptive title or chapter heading.
    Provide ONLY the JSON outline with no additional text or explanation.
    Use double quotes for all strings.
    """
    
    try:
        outline, prompt_token_count, candidates_token_count = get_response(outline_prompt, chat)
        logger.info(f"Outline: {outline}")
        
        # Clean up the response
        if isinstance(outline, str):
            # First, extract just the JSON content if it's wrapped in code blocks
            if '```json' in outline:
                # Extract content between ```json and ```
                start = outline.find('```json') + 7  # length of ```json
                end = outline.rfind('```')
                outline = outline[start:end].strip()
            
            try:
                outline_dict = json.loads(outline)
            except json.JSONDecodeError:
                # If that fails, try additional cleaning
                outline = outline.strip()  # Remove any leading/trailing whitespace
                outline = outline.replace('\n', '')  # Remove newlines
                outline = outline.replace('  ', '')  # Remove extra spaces
                try:
                    outline_dict = json.loads(outline)
                except json.JSONDecodeError as e:
                    logger.error(f"Failed to parse outline as JSON after cleaning: {str(e)}")
                    logger.error(f"Cleaned outline string: {outline}")
                    raise
        else:
            outline_dict = outline

        # Validate the structure
        is_valid, error_msg = validate_outline_structure(outline_dict, age_group)
        if is_valid:
            # Save the title to the story instance right after validating the outline
            story_instance.outline = json.dumps(outline_dict)
            story_instance.title = outline_dict['title']
            story_instance.save(update_fields=['title', 'outline'])
            return outline_dict, chat, prompt_token_count, candidates_token_count
        else:
            logger.error(f"Invalid outline structure: {error_msg}")
            # Try to fix the format
            try:
                logger.info("Attempting to fix outline format...")
                fixed_outline = fix_outline_format(outline_dict, age_group)
                return fixed_outline, chat
            except Exception as fix_error:
                logger.error(f"Failed to fix outline format: {str(fix_error)}")
                raise
                
    except Exception as e:
        logger.error(f"Error in get_outline: {str(e)}")
        raise RuntimeError("Failed to generate valid outline")

   
def validate_outline_structure(outline, age_group, path="root"):
    """
    Validates if the outline matches the expected structure for the given age_group.
    """
    try:
            
        # Check if outline is a dictionary
        if not isinstance(outline, dict):
            return False, f"Error: {path} is not a dictionary, but {type(outline).__name__}"

        # For root level, check title and parts
        if path == "root":
            if "title" not in outline:
                return False, "Missing title key"
            
            # Check for required parts based on age group
            required_parts = []
            if age_group == '3 through 6':
                required_parts = ["Part 1", "Part 2"]
            elif age_group == '5 through 8':
                required_parts = ["Part 1", "Part 2"]
            elif age_group == '7 through 11':
                required_parts = ["Part 1", "Part 2", "Part 3"]
            elif age_group == '10 through 13':
                required_parts = ["Part 1", "Part 2", "Part 3", "Part 4"]
            else:  # '13 through 18'
                required_parts = ["Part 1", "Part 2", "Part 3", "Part 4", "Part 5"]
            
            for part in required_parts:
                if part not in outline:
                    return False, f"Missing {part}"
                
                # Validate chapters in each part
                chapters = outline[part]
                if not isinstance(chapters, dict):
                    return False, f"{part} should be a dictionary"
                
                required_chapters = []
                if age_group == '3 through 6':
                    required_chapters = ["Chapter 1", "Chapter 2", "Chapter 3"]
                else:
                    required_chapters = ["Chapter 1", "Chapter 2", "Chapter 3", "Chapter 4", "Chapter 5"]
                
                for chapter in required_chapters:
                    if chapter not in chapters:
                        return False, f"Missing {chapter} in {part}"
                    if not isinstance(chapters[chapter], str):
                        return False, f"{part}/{chapter} should be a string"
                    if not chapters[chapter].strip():
                        return False, f"{part}/{chapter} is empty"

        return True, None

    except Exception as e:
        return False, f"Validation error: {str(e)}"


def write_story(outline, age_group, chat, prompt, story_instance):
    """
    Writes a story based on the validated outline structure, maintaining a running summary.
    """
    try:
        logger.debug("Starting story writing process...")
        summary = "This is the first chapter. "  # Initialize summary
        
        # Define structure based on age format
        if age_group == '3 through 6':
            num_parts = 2
            num_chapters = 3
        elif age_group == '5 through 8':
            num_parts = 2
            num_chapters = 5
        elif age_group == '7 through 11':
            num_parts = 3
            num_chapters = 5
        elif age_group == '10 through 13':
            num_parts = 4
            num_chapters = 5
        else:  # '13 through 18'
            num_parts = 5
            num_chapters = 5

        if age_group == '3 through 6':
            num_words = 150
        elif age_group == '5 through 8':
            num_words = 200
        elif age_group == '7 through 11':
            num_words = 250
        elif age_group == '10 through 13':
            num_words = 250
        else:  # '13 through 18'
            num_words = 300
            
        # Create a separate model instance for summaries
        summary_model = genai.GenerativeModel(
            model_name='gemini-1.5-pro',
            generation_config={
                'temperature': 0.3,  # Lower temperature for more focused summaries
                'top_p': 0.8,
                'top_k': 40,
            }
        )
            
        # Iterate through the structure
        prompt_token_count = 0
        candidates_token_count = 0
        last_summary = "1st chapter"
        rules = get_bucket_data('write-456414.appspot.com', 'rules3.txt')
        for part_num in range(1, num_parts + 1):
            part_key = f"Part {part_num}"
            part_chapters = outline[part_key]
            
            for chapter_num in range(1, num_chapters + 1):
                chapter_key = f"Chapter {chapter_num}"
                chapter_title = part_chapters[chapter_key]
                
                chapter_prompt = f"""
                Now write the content for {part_key}, {chapter_key}: "{chapter_title}"
                
                Story context so far: {summary}
                
                Remember:
                - This is part of the story about: {prompt}, the title is: {story_instance.title}, and the outline is: {story_instance.outline}.
                - This is Part {part_num} of {num_parts}, Chapter {chapter_num} of {num_chapters}
                - The chapter should follow from the previous content
                - Keep the style and tone consistent with the age group {age_group}
                - The chapter should be about {num_words} words
                - You are an expert assistant that provides direct and concise responses
                - Do not include any introductory or conversational phrases such as 'Sure, here is a...', 'Here's the information you requested:', etc.
                - Your responses should consist solely of the requested information or text, without any additional commentary or framing
                - Ensure that the output contains only the actual content and nothing else
                - Follow these rules as you construct the story: {rules}
                """
                
                logger.debug(f"Generating content for {part_key}, {chapter_key}")
                chapter_content, chapter_prompt_count, chapter_candidates_count = get_response(chapter_prompt, chat)
                prompt_token_count += chapter_prompt_count
                candidates_token_count += chapter_candidates_count
                # Add chapter to full story
                
                              
                # Get and remove last message from chat history
                chat_length = len(chat.history)
                chat.history.pop(chat_length - 1)
                
                # Generate summary of this chapter
                summary_prompt = f"""
                You are writing a story about: {prompt}
                The summary response from the previous chapter: {last_summary}
                The content generated here will be for your own reference. 
                Write and organize this response in the most concise way that you can still reference it easily.
                Each of these repsponses will be presented back to you to continue writing. 
                They will also be collected for another instance of your model to reference. They are not for the reader.
                Please summarize the current chapter content concisely:
                {chapter_content}
                Add a note at the end to tell yourself about any plot elements that need to be continued or built upon based on the writing rules.    
                Cross reference the previous summary and notes with the current chapter to write notes for the next chapter
                """
                
                summary_response = summary_model.generate_content(summary_prompt)
                summary_prompt_count = summary_response.usage_metadata.prompt_token_count
                summary_candidates_count = summary_response.usage_metadata.candidates_token_count
                prompt_token_count += summary_prompt_count
                candidates_token_count += summary_candidates_count
                chapter_summary = summary_response.text.strip()
                
                # Clean the summary (remove any markdown, quotes, etc.)
                chapter_summary = chapter_summary.strip('`').strip('"').strip("'")
                chapter_summary = chapter_summary.replace('\n', ' ').strip()
    
                
                # Get or create StoryContent instance for this story
                story_content, created = StoryContent.objects.get_or_create(story=story_instance)

                # Initialize the part in raw_content if it doesn't exist
                if part_key not in story_content.raw_content:
                    story_content.raw_content[part_key] = {}

                # Add the chapter content and summary
                story_content.raw_content[part_key][chapter_key] = {
                    'full_text': chapter_content,
                    'summary': chapter_summary
                }

                # Save the changes
                story_content.save()
                
                logger.debug(f"Updated summary after {part_key}, {chapter_key}")
                count = 0
                for i in range(5):
                    try:
                        image_prompt = f"""Choose an element of this story summary: {chapter_summary}.
                                        Describe it visually as you would to someone not there.""" 
                        image_prompt_response = summary_model.generate_content(image_prompt)
                        image_prompt_count = image_prompt_response.usage_metadata.prompt_token_count
                        image_candidates_count = image_prompt_response.usage_metadata.candidates_token_count
                        prompt_token_count += image_prompt_count
                        candidates_token_count += image_candidates_count
                        chapter_image_prompt = image_prompt_response.text.strip()
                        
                        # Clean the summary (remove any markdown, quotes, etc.)
                        chapter_image_prompt = chapter_image_prompt.strip('`').strip('"').strip("'").strip('*').strip('#')
                        chapter_image_prompt = chapter_image_prompt.replace('\n', ' ').strip()
                    
                        prompt = f"Create an image of:" + chapter_image_prompt
                        
                        # Generate chapter-specific image
                        generate_and_store_image(
                            story_instance, 
                            prompt, 
                            part_key=part_key, 
                            chapter_key=chapter_key
                        )
                        
                        logger.debug(f"Generated image for story {story_instance.id}, {part_key}, {chapter_key}")
                    except Exception as e:
                        count += 1
                        logger.error(f"Error {count} making chapter image for {story_instance.id}, {part_key}, {chapter_key}: {str(e)}")
                        exponential_backoff(count)
                
                # Set new last summary and image prompt  
                last_summary = chapter_summary
                # Add to running summary
                summary += f"{chapter_summary} "
        logger.info("Story writing completed successfully")
        
        final_prompt_token_count, final_candidates_token_count = create_story_summary(story_instance, summary)
        prompt_token_count += final_prompt_token_count
        candidates_token_count += final_candidates_token_count
        # Return only the story content
        return prompt_token_count, candidates_token_count
        
    except Exception as e:
        logger.error(f"Error in write_story: {str(e)}", exc_info=True)
        raise

def exponential_backoff(attempt, max_delay=120):
    """Implements exponential backoff for retries."""
    delay = min(max_delay, (2 ** attempt) + random.uniform(0, 1))
    time.sleep(delay)

def create_story_summary(story_instance, full_summary):
    """Creates and saves a concise 2-sentence summary directly to the story instance."""
    try:
        # Create a new model instance for the summary
        model = genai.GenerativeModel(
            model_name='gemini-1.5-pro',
            generation_config={
                'temperature': 0.3,
                'top_p': 0.8,
                'top_k': 40,
            }
        )
        
        summary_prompt = f"""
        Create a compelling 2 to 3 sentence summary of this story:
        {full_summary}
        
        Provide ONLY the summary with no additional text or formatting.
        """
        
        # Add debug logging
        logger.debug(f"Generating summary for story {story_instance.id}")
        logger.debug(f"Story instance before summary: {story_instance.__dict__}")
        
        response = model.generate_content(summary_prompt)
        prompt_token_count = response.usage_metadata.prompt_token_count
        candidates_token_count = response.usage_metadata.candidates_token_count
        short_summary = response.text.strip()
        
        # Clean the summary
        short_summary = short_summary.strip('`').strip('"').strip("'")
        short_summary = short_summary.replace('\n', ' ').strip()
        logger.info(f"Summary content: {short_summary}")
        # Add debug logging for the summary
        logger.debug(f"Generated summary: {short_summary}")
        
        # Save directly to the story instance
        story_instance.summary = short_summary
        story_instance.save(update_fields=['summary'])  # Explicitly specify field to update
        logger.info(f"Successfully created and saved summary for story {story_instance.id}")
        # Generate and store cover image
        count = 0
        for i in range(5):
            try:
                image_prompt = f"""Pick an element from this story summary: {short_summary}.
                                    Descride this choice visually as you would to someone not there.""" 
                image_prompt_response = model.generate_content(image_prompt)
                image_prompt_count = image_prompt_response.usage_metadata.prompt_token_count
                image_candidates_count = image_prompt_response.usage_metadata.candidates_token_count
                prompt_token_count += image_prompt_count
                candidates_token_count += image_candidates_count
                chapter_image_prompt = image_prompt_response.text.strip()
                chapter_image_prompt = chapter_image_prompt.strip('`').strip('"').strip("'").strip('*').strip('#')
                chapter_image_prompt = chapter_image_prompt.replace('\n', ' ').strip()
                    
                    
                prompt = f"Create an image of: " + chapter_image_prompt
                       
                # Generate chapter-specific image
                generate_and_store_image(
                    story_instance, 
                    prompt
                )
                logger.debug(f"Generated cover image for story {story_instance.id}")
            except Exception as e:
                count += 1
                logger.error(f"Error {count} making cover image for {story_instance.id}: {str(e)}")
                exponential_backoff(count)
        
        success = add_image_data(story_instance)
        if not success:
            logger.error(f"Failed to add cover data for story {story_instance.id}")
        return prompt_token_count, candidates_token_count

    except Exception as e:
        logger.error(f"Error creating story summary: {str(e)}")
        pass  # Continue execution even if summary creation fails

