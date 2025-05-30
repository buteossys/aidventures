from django.core import serializers
import json
from .models import Adventure, Story

def get_adventure_story_data(adventure_id=7, story_id=3):
    """
    Fetch and display data for specific adventure and story IDs
    """
    try:
        # Get the adventure with all its data
        adventure = Adventure.objects.get(id=adventure_id)
        story = Story.objects.get(id=story_id, adventure=adventure)
        
        # Create a structured dictionary of the data
        data = {
            'adventure': {
                'id': adventure.id,
                'user': adventure.user.username,
                'adventure_number': adventure.adventure_number,
                'created_at': adventure.created_at.isoformat(),
                'style_data': adventure.style_data,
                'world_data': adventure.world_data,
                'character_data': adventure.character_data,
                'setting_data': adventure.setting_data
            },
            'story': {
                'id': story.id,
                'prompt': story.prompt,
                'created_at': story.created_at.isoformat(),
                'outline': story.outline,
                'summary': story.summary,
                'raw_file': story.raw_file,
            }
        }
        
        # Print formatted JSON to terminal
        print("\n=== Adventure and Story Data ===")
        print(json.dumps(data, indent=2))
        
        return data
        
    except Adventure.DoesNotExist:
        print(f"Adventure with ID {adventure_id} not found")
        return None
    except Story.DoesNotExist:
        print(f"Story with ID {story_id} not found for Adventure {adventure_id}")
        return None
    except Exception as e:
        print(f"Error fetching data: {str(e)}")
        import traceback
        print(traceback.format_exc())
        return None

# Execute the function when this file is run directly
if __name__ == "__main__":
    get_adventure_story_data()
