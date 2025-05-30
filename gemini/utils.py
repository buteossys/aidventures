import os
import json
import time
from gemini.models import Adventure
import logging
import random
from google.cloud import aiplatform
from vertexai.generative_models import GenerativeModel
import logging
from google.cloud import storage

logger = logging.getLogger(__name__)

# It's best practice to define these as environment variables
PROJECT_ID = os.environ.get("GOOGLE_CLOUD_PROJECT")
LOCATION = os.environ.get("VERTEX_AI_LOCATION", "us-central1") # Default location if not set

def initialize_vertex_ai():
    """Initializes the Vertex AI SDK and returns a GenerativeModel instance."""
    if not PROJECT_ID:
        logger.error("GOOGLE_CLOUD_PROJECT environment variable not set.")
        raise ValueError("GOOGLE_CLOUD_PROJECT environment variable must be set.")

    try:
        aiplatform.init(project=PROJECT_ID, location=LOCATION)
        logger.info(f"Vertex AI initialized for project {PROJECT_ID} in {LOCATION}")
        system_data = get_system_instructions()
        model = GenerativeModel(
            model_name="gemini-2.0-flash",
            system_instruction=[system_data]
        )
        return model
    except Exception as e:
        logger.error(f"Error initializing Vertex AI: {e}")
        raise

def get_system_instructions():
    # Initialize the storage client
    storage_client = storage.Client()
    
    # Get the bucket
    bucket_name = 'write-res'
    bucket = storage_client.bucket(bucket_name)
    
    # Get the blob (file)
    blob = bucket.blob('system_instructions.json')
    
    # Download and read the content
    system_data = blob.download_as_text()
    return system_data

def get_response(prompt, model):
    try:
        logger.info(f"Making Vertex AI request with prompt length: {len(prompt)}")
        start_time = time.time()
        
        # Generate content using the model
        response = model.generate_content(
            prompt,
            generation_config={
                "temperature": 0.7,
                "top_p": 0.8,
                "top_k": 40,
                "max_output_tokens": 2048,
            }
        )
        
        duration = time.time() - start_time
        logger.info(f"Vertex AI request completed in {duration:.2f} seconds")
        
        return response.text
    except Exception as e:
        logger.error(f"Vertex AI request failed: {str(e)}")
        logger.error(f"Request details - Prompt length: {len(prompt)}")
        raise

def format_cache_data(adventure_id):
    with open('gemini/static/gemini/data/rules.txt', 'r') as f: 
        rules_data = f.read()
    with open('gemini/static/gemini/data/example.txt', 'r') as f: 
        example_data = f.read()
    adventure = Adventure.objects.get(id=adventure_id)
    adventure_data = {
        'style': adventure.style_data,
        'world': adventure.world_data,
        'characters': adventure.character_data,
        'settings': adventure.setting_data
    }
    adventure_data = json.dumps(adventure_data)
    cache_data = ''.join([rules_data+'\n'+example_data+'\n'+adventure_data])
    return cache_data

#def create_cache(cache_data):
#    with open('gemini/static/gemini/data/system_instructions.json', 'r') as f: 
#        system_data = f.read()
#    display_name = str(datetime.datetime.now()) + '_staging'
 #   content_cache = client.caches.create(
 #       model='models/gemini-1.5-pro-002',
 #       config=CreateCachedContentConfig(
 #           display_name= display_name, 
 #           system_instruction= system_data,
 #           contents= cache_data,
 #           ttl='900s',
 #       ))
 #   return content_cache.name
    

def get_outline(story_prompt, model):
    outline_prompt = f"""Create an outline for a story that takes place in the world described in the model cache. This story will be about: {story_prompt}"""
    max_retries = 5
    for retry in range(max_retries):
        try:
            outline = get_response(outline_prompt, model)
        except Exception as e:
            logger.error(f"Attempt {retry+1} of {max_retries} failed: Error in write_story: {str(e)}")
            if retry < max_retries - 1:
                time.sleep(1)
            else:
                raise RuntimeError
    if outline.startswith('```json'):
        outline = outline.strip('`json')
        try:
            outline_dict = json.loads(outline)
            return outline_dict
        except: 
            return outline
    else:
        outline = outline.strip('#*')
        try:
            outline_dict = json.loads(outline)
            return outline_dict
        except:
            return outline

def write_story_dict(outline, model, read_time, prompt):
    try:
        # Outline is a dictionary
        outline_string = str(outline)  # Get the outline part
        title = outline['title']
        # Set story variables
        full_story_raw = title + '\n' + '\n'
        #temp_cache = 'This is the first chapter of the story.'
        
        # Write the story
        if read_time in ('5 minutes', '10 minutes'):
            for index, key in enumerate(outline):
                if index > 0:
                    rag_prompt = f"""
                        You are generating the scene in the story for {key}.
                        Here is the original prompt: {prompt}
                        Here is the full outline: {outline_string}
                        """
                        #Here is context from previously generated content: {temp_cache}
                        #"""
                    max_retries = 5
                    for retry in range(max_retries):
                        try:
                            content = get_response(rag_prompt, model)
                            break
                        except Exception as e:
                            logger.error(f"Attempt {retry+1} of {max_retries} failed: Error in write_story: {str(e)}")
                            if retry < max_retries - 1:
                                exponential_backoff(retry)
                            else:
                                raise RuntimeError
                    try:
                        content_string = content.strip('*')
                        full_story_raw = ''.join([full_story_raw, key, '\n', '\n', content_string, '\n'])
                        time.sleep(1)
                    except:
                        raise RuntimeError
        elif read_time in ('15 minutes', '30 minutes'):
            for index, key in enumerate(outline):
                if index > 0:
                    part_key = str(key)
                    full_story_raw = ''.join([full_story_raw, part_key, '\n', '\n'])
                    for key in outline[key]:
                        rag_prompt = f"""
                            You are generating the scene in the story for {part_key}, {key}.
                            Here is the original prompt: {prompt}
                            Here is the full outline: {outline}
                            """
                            #Here is context from previously generated content: {temp_cache}
                            #"""
                        max_retries = 5
                        for retry in range(max_retries):
                            try:
                                content = get_response(rag_prompt, model)
                                break
                            except Exception as e:
                                logger.error(f"Attempt {retry+1} of {max_retries} failed: Error in write_story: {str(e)}")
                                if retry < max_retries - 1:
                                    exponential_backoff(retry)
                                else:
                                    raise RuntimeError
                        try:
                            content_string = content.strip('*')
                            full_story_raw = ''.join([full_story_raw, key, '\n', '\n', content_string, '\n'])
                            time.sleep(1) 
                        except:
                            raise RuntimeError
        else: 
            raise ValueError(f"Invalid read_time value: {read_time}")

        # Return all data needed for the Story model
        return full_story_raw
        
    except json.JSONDecodeError as e:
        logger.error(f"JSON Error in write_story: {str(e)}")
        logger.error(f"Raw outline:\n{outline}")
        raise ValueError(f"Failed to parse story outline: {str(e)}")
    except KeyError as e:
        logger.error(f"Missing key in outline: {str(e)}")
        logger.error(f"Outline dict: {outline}")
        raise ValueError(f"Missing required field in outline: {str(e)}")
    except Exception as e:
        logger.error(f"Error in write_story: {str(e)}")
        raise


def write_story_string(outline, model, read_time, prompt):
    try:
        #temp_cache = 'This is the first chapter of the story.'
        full_story_raw = ''
        # Write the story
        if read_time in ('5 minutes', '10 minutes'):
            for i in range(6):
                rag_prompt = f"""
                    You are generating the scene in the story for chapter {i}.
                    Here is the original prompt: {prompt}
                    Here is the full outline: {outline}
                    """
                    #Here is context from previously generated content: {temp_cache}
                    #"""
                max_retries = 5
                for retry in range(max_retries):
                    try:
                        content = get_response(rag_prompt, model)
                        break
                    except Exception as e:
                        logger.error(f"Attempt {retry+1} of {max_retries} failed: Error in write_story: {str(e)}")
                        if retry < max_retries - 1:
                            exponential_backoff(retry)
                        else:
                            raise RuntimeError
                try:
                    content_string = content.strip('*')
                    full_story_raw = ''.join([full_story_raw, '\n', '\n', content_string, '\n'])
                    time.sleep(30) 
                except:
                    raise RuntimeError
        elif read_time in ('15 minutes', '30 minutes'):
            for i in range(3):
                part_key = str(i)
                full_story_raw = ''.join([full_story_raw, 'Part ', part_key, '\n', '\n'])
                for i in range(3):
                    rag_prompt = f"""
                        You are generating the scene in the story for {part_key}, Chapter {i}.
                        Here is the original prompt: {prompt}
                        Here is the full outline: {outline}
                        """
                        #Here is context from previously generated content: {temp_cache}
                        #"""
                    max_retries = 5
                    for retry in range(max_retries):
                        try:
                            content = get_response(rag_prompt, model)
                            break
                        except Exception as e:
                            logger.error(f"Attempt {retry+1} of {max_retries} failed: Error in write_story: {str(e)}")
                            if retry < max_retries - 1:
                                exponential_backoff(retry)
                            else:
                                raise RuntimeError
                    try:
                        content_string = content.strip('*')
                        full_story_raw = ''.join([full_story_raw, '\n', '\n', content_string, '\n'])
                        time.sleep(30) 
                    except:
                        raise RuntimeError
        else: 
            raise ValueError(f"Invalid read_time value: {read_time}")

        return full_story_raw
    except json.JSONDecodeError as e:
        logger.error(f"JSON Error in write_story: {str(e)}")
        logger.error(f"Raw outline:\n{outline}")
        raise ValueError(f"Failed to parse story outline: {str(e)}")
    except KeyError as e:
        logger.error(f"Missing key in outline: {str(e)}")
        logger.error(f"Outline dict: {outline}")
        raise ValueError(f"Missing required field in outline: {str(e)}")
    except Exception as e:
        logger.error(f"Error in write_story: {str(e)}")
        raise

def exponential_backoff(attempt, max_delay=120):
    delay = min(max_delay, (2 ** attempt) + random.uniform(0, 1))
    time.sleep(delay)