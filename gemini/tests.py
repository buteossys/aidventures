from django.test import TestCase
from django.contrib.auth.models import User
from gemini.models import Adventure, Story
from django.utils import timezone
import json

def cleanup_test_data():
    # Delete test user and related data
    User.objects.filter(username='test@test.com').delete()
    print("Test data cleaned up")

# Create your tests here.

def create_test_data():
    # Clean up any existing test data first
    cleanup_test_data()
    
    # Get or create test user
    user, created = User.objects.get_or_create(
        username='test@test.com',
        email='test@test.com'
    )
    if created:
        user.set_password('testPass1')
        user.save()

    # Create an Adventure
    adventure = Adventure.objects.create(
        user=user,
        adventure_number=2,
        style_data={
            'age_group': '7 through 11',
            'gender': 'all',
            'genre': 'fantasy',
            'tone': 'humourous'
        },
        world_data={
            'temporal': 'in the present',
            'general': 'A magical world hidden within our own, where ordinary objects can come to life.',
            'backstory': 'For centuries, certain people have had the ability to bring inanimate objects to life through their imagination.',
            'current_events': 'Recently, more and more children have been discovering this ability, leading to both wonderful and chaotic situations.'
        },
        character_data=[
            {
                'name': 'Lucy Thompson',
                'gender': 'female',
                'age': 10,
                'species': 'Human',
                'role': 'protagonist',
                'description': 'A curious girl with wild curly hair and bright green eyes',
                'about': 'Lucy loves to draw and recently discovered she can bring her drawings to life.'
            },
            {
                'name': 'Mr. Pencil',
                'gender': 'not specified',
                'age': 1,
                'species': 'Animated Object',
                'role': 'friend of a main character',
                'description': 'A walking, talking pencil with a mustache drawn on its eraser',
                'about': 'The first object Lucy ever brought to life, now her loyal friend and advisor.'
            }
        ],
        setting_data=[
            {
                'use_type': 'primary',
                'general_location': 'in or next to a forest',
                'specific_location': 'in a small town',
                'weather': 'mild most of the time',
                'about': 'A cozy town called Doodleton, where Lucy lives with her family. The town is surrounded by a mysterious forest where animated objects often go to play.'
            }
        ]
    )

    # Create a Story
    story = Story.objects.create(
        adventure=adventure,
        prompt="Write a story about Lucy and Mr. Pencil having an adventure in the magical forest where they discover a whole society of animated art supplies.",
        title="The Secret Society of Art Supplies",
        outline=json.dumps({
            "title": "The Secret Society of Art Supplies",
            "chapter1": "Lucy and Mr. Pencil discover strange markings in the forest",
            "chapter2": "Following the trail of colorful footprints",
            "chapter3": "The hidden village of art supplies",
            "chapter4": "Making new friends and learning secrets"
        }),

        status='completed',
        created_at=timezone.now(),
        updated_at=timezone.now()
    )

    print(f"Created Adventure ID: {adventure.id}")
    print(f"Created Story ID: {story.id}")
    return adventure, story

# You can run this script in Django shell:
# python manage.py shell
# from gemini.models import create_test_data
# adventure, story = create_test_data()
