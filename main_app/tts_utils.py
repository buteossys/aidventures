import io
import os
import logging
from typing import List, Dict, Tuple, Optional

# Ensure google-cloud-texttospeech is installed
# pip install google-cloud-texttospeech
from google.cloud import texttospeech
from google.api_core import exceptions as google_exceptions
from google.cloud import storage
from django.contrib.auth import get_user_model

User = get_user_model()  # This will get your custom User model from access.User

# --- Configuration ---

# Google TTS API has limits (around 5000 bytes, UTF-8 encoded).
# We chunk text safely below this limit. 4500 characters is generally safe.
MAX_CHUNK_SIZE = 4500

# Define some popular voices. You can find more via client.list_voices()
# Format: { 'display_name': 'voice_name (language_code)', ... }
# See: https://cloud.google.com/text-to-speech/docs/voices
POPULAR_VOICES = {
    "US English Female (Natural)": "en-US-Neural2-C",
    "US English Male (Natural)": "en-US-Neural2-D",
    "US English Female (WaveNet)": "en-US-Wavenet-F",
    "US English Male (WaveNet)": "en-US-Wavenet-D",
    "GB English Female (Natural)": "en-GB-Neural2-C",
    "GB English Male (Natural)": "en-GB-Neural2-D",
    "GB English Female (News)": "en-GB-News-K", # Good for narration
    "Australian Female (Natural)": "en-AU-Neural2-C",
    "Australian Male (Natural)": "en-AU-Neural2-D",
    # Add other languages/voices as needed
    "Spanish (US) Female (Natural)": "es-US-Neural2-C",
    "French Female (Natural)": "fr-FR-Neural2-C",
    "German Female (Natural)": "de-DE-Neural2-F",
}

# --- Setup Logging ---
logger = logging.getLogger(__name__)

# --- Helper Functions ---

def get_tts_client() -> Optional[texttospeech.TextToSpeechClient]:
    """
    Initializes and returns a TextToSpeechClient using Application Default Credentials (ADC).

    ADC automatically finds credentials in the following order:
    1. GOOGLE_APPLICATION_CREDENTIALS environment variable.
    2. Credentials from gcloud auth application-default login.
    3. Attached service account credentials (on App Engine, GCE, Cloud Run, etc.).
    """
    try:
        # Initialize client without explicit credentials.
        # It will use ADC to find credentials automatically.
        tts_client = texttospeech.TextToSpeechClient()
        logger.info("TextToSpeechClient initialized successfully using Application Default Credentials.")
        return tts_client
    except google_exceptions.DefaultCredentialsError as e:
         logger.error(f"Could not find Application Default Credentials. "
                      f"Ensure you are running on GCP with an attached service account, "
                      f"have set GOOGLE_APPLICATION_CREDENTIALS, or have run "
                      f"'gcloud auth application-default login'. Error: {e}", exc_info=True)
         return None
    except Exception as e:
         logger.error(f"Failed to initialize TextToSpeechClient: {e}", exc_info=True)
         return None

def get_voice_details(voice_name: str) -> Optional[Tuple[str, str]]:
    """
    Extracts language code and base voice name.
    Assumes voice_name format like 'en-US-Wavenet-F'.
    Returns (language_code, base_voice_name) or None if format is wrong.
    """
    parts = voice_name.split('-')
    if len(parts) >= 2:
        language_code = f"{parts[0]}-{parts[1]}"
        # The rest is considered the 'name' part for the API
        base_voice_name = voice_name
        return language_code, base_voice_name
    else:
        logger.warning(f"Could not parse language code from voice_name: {voice_name}")
        return None

def split_text_into_chunks(text: str, max_length: int = 4500) -> List[str]:
    """
    Split text into chunks that are suitable for the Text-to-Speech API.
    Each chunk will be at most max_length characters and will try to break at sentence boundaries.
    
    Args:
        text (str): The text to split
        max_length (int): Maximum length of each chunk (default 4500)
        
    Returns:
        List[str]: List of text chunks
    """
    if not text:
        return []

    # Initialize chunks list
    chunks = []
    
    # Process text while there's still content
    while text:
        if len(text) <= max_length:
            chunks.append(text)
            break
            
        # Find the last sentence boundary within max_length
        chunk_end = max_length
        for ending in ['. ', '! ', '? ']:
            last_period = text[:max_length].rfind(ending)
            if last_period != -1:
                chunk_end = last_period + 2  # Include the period and space
                break
                
        # If no sentence boundary found, try to break at last space
        if chunk_end == max_length:
            last_space = text[:max_length].rfind(' ')
            if last_space != -1:
                chunk_end = last_space + 1
        
        # Extract chunk and update remaining text
        chunk = text[:chunk_end].strip()
        if chunk:
            chunks.append(chunk)
        text = text[chunk_end:].strip()
    
    return chunks


# --- Core Synthesis Functions ---

def synthesize_single_chunk(
    client: texttospeech.TextToSpeechClient,
    text_chunk: str,
    voice_name: str,
    audio_format: texttospeech.AudioEncoding = texttospeech.AudioEncoding.MP3
) -> Optional[bytes]:
    """Synthesizes audio for a single text chunk (must be under API limit)."""
    voice_details = get_voice_details(voice_name)
    if not voice_details:
        logger.error(f"Invalid voice_name format: {voice_name}")
        return None
    language_code, base_voice_name = voice_details

    synthesis_input = texttospeech.SynthesisInput(text=text_chunk)

    voice = texttospeech.VoiceSelectionParams(
        language_code=language_code,
        name=base_voice_name
    )

    # Select the type of audio file you want returned (MP3, LINEAR16, OGG_OPUS)
    audio_config = texttospeech.AudioConfig(
        audio_encoding=audio_format
        # You can add speaking_rate, pitch, effects_profile_id etc. here
        # speaking_rate=1.0, # Default is 1.0
        # pitch=0,         # Default is 0
    )

    try:
        response = client.synthesize_speech(
            input=synthesis_input, voice=voice, audio_config=audio_config
        )
        logger.debug(f"Successfully synthesized chunk starting with: {text_chunk[:50]}...")
        return response.audio_content
    except google_exceptions.InvalidArgument as e:
        logger.error(f"Invalid argument during synthesis for chunk: {text_chunk[:50]}... Error: {e}", exc_info=True)
        # This often happens if the chunk is too large or contains unsupported characters
        return None
    except Exception as e:
        logger.error(f"Error during TTS synthesis for chunk: {text_chunk[:50]}... Error: {e}", exc_info=True)
        return None


def synthesize_long_text(text: str, voice_name: str, story_id: int, user_id: int, adventure_id: int):
    try:
        # Get the username using your custom User model
        user = User.objects.get(id=user_id)
        username = user.username
        
        # Use username in the file path
        output_filename = f"{username}/adventure_{adventure_id}/story_{story_id}/audio.mp3"
        
        # Check if file already exists
        storage_client = storage.Client()
        bucket = storage_client.bucket('write-res')
        blob = bucket.blob(output_filename)
        
        if blob.exists():
            logger.info(f"Audio file already exists: {output_filename}")
            return
            
        # Rest of the function remains the same...
        client = texttospeech.TextToSpeechClient()
        
        # Split text into chunks if needed
        text_chunks = split_text_into_chunks(text)
        all_audio_content = []
        
        for chunk in text_chunks:
            synthesis_input = texttospeech.SynthesisInput(text=chunk)
            voice = texttospeech.VoiceSelectionParams(
                language_code=voice_name[:5],
                name=voice_name
            )
            audio_config = texttospeech.AudioConfig(
                audio_encoding=texttospeech.AudioEncoding.MP3
            )
            
            response = client.synthesize_speech(
                input=synthesis_input,
                voice=voice,
                audio_config=audio_config
            )
            all_audio_content.append(response.audio_content)
        
        # Combine all audio content
        combined_audio = b''.join(all_audio_content)
        
        # Upload to Google Cloud Storage
        blob.upload_from_string(
            combined_audio,
            content_type='audio/mpeg'
        )
        
        logger.info(f"Successfully generated and uploaded audio file: {output_filename}")
        
    except Exception as e:
        logger.error(f"Error in synthesize_long_text: {str(e)}", exc_info=True)
        raise

# --- Public Accessors ---

def get_available_voices() -> Dict[str, str]:
    """Returns the predefined list of popular voices."""
    # You could potentially expand this to actually query the API
    # using client.list_voices() if needed, but that's an extra API call.
    return POPULAR_VOICES


# --- Example Usage (for testing locally) ---
if __name__ == '__main__':
    print("--- Running TTS Utils Test (using Application Default Credentials) ---")

    # IMPORTANT: For this test to run locally, you need:
    # 1. `pip install google-cloud-texttospeech`
    # 2. To be authenticated via Application Default Credentials (ADC). Choose ONE:
    #    a) Run `gcloud auth application-default login` in your terminal. This uses your user credentials.
    #    b) Download a service account key JSON file, and set the environment variable:
    #       export GOOGLE_APPLICATION_CREDENTIALS="/path/to/your/keyfile.json"
    #       (Ensure this service account has permissions for Text-to-Speech API)
    # 3. Ensure the Text-to-Speech API is enabled in your Google Cloud project associated with the credentials.

    logging.basicConfig(level=logging.INFO) # Show logs during test

    # Attempt to get client to check if ADC is working locally
    client_test = get_tts_client()
    if not client_test:
        print("\nERROR: Failed to get TTS client. Please check your ADC setup (see comments above) and ensure the TTS API is enabled.")
        exit()
    else:
        print("\nSuccessfully obtained TTS client via ADC.")

    print("\nAvailable Voices:")
    voices = get_available_voices()
    for display, name in voices.items():
        print(f"- {display}: {name}")

    # --- Test Long Text Synthesis ---
    print("\nTesting Long Text Synthesis...")
    paragraph = "This is a paragraph of text that will be repeated multiple times to simulate a long document suitable for text-to-speech conversion. This version of the utility uses Application Default Credentials for authentication, simplifying deployment to Google Cloud environments like App Engine where a service account is attached. Locally, ensure you've authenticated via gcloud or set the GOOGLE_APPLICATION_CREDENTIALS environment variable. Handling long text still requires splitting it into manageable chunks due to API limits. "
    long_text_sample = paragraph * 80 # Approx 40k chars
    print(f"Sample text length: {len(long_text_sample)} characters (approx {len(long_text_sample.split())} words)")


    selected_voice = POPULAR_VOICES["GB English Female (News)"] # Example voice

    audio_bytes = synthesize_long_text(long_text_sample, voice_name=selected_voice)

    if audio_bytes:
        output_filename = "test_output_adc.mp3"
        try:
            with open(output_filename, "wb") as f:
                f.write(audio_bytes)
            print(f"\nSUCCESS: Synthesized audio saved to {output_filename} ({len(audio_bytes)} bytes)")
            print("You can now play this file with an audio player.")
        except IOError as e:
             print(f"\nERROR: Could not write output file '{output_filename}'. Check permissions. Error: {e}")
    else:
        print("\nFAILED: Audio synthesis did not complete successfully. Check logs for errors (permissions, API enabled, etc.).")

    print("\n--- TTS Utils Test Complete ---")