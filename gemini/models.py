from django.db import models
from django.contrib.auth.models import User
from django.db.models import JSONField  # Use this for PostgreSQL or Django 3.1+
from django.core.exceptions import ValidationError
from django.conf import settings
#choices
age_group_choices = [
    ('3 through 6', '3 to 6'),
    ('5 through 8', '5 to 8'),
    ('7 through 11', '7 to 11'),
    ('10 through 13', '10 to 13'),
    ('13 through 18', '13+'),
    ]
style_gender_choices = [
    ('female', 'Girl'),
    ('male', 'Boy'),
    ('all', 'Both'),
    ]
character_gender_choices = [
    ('female', 'Girl'),
    ('male', 'Boy'),
    ('not specified', 'Other'),
]
genre_choices = [
    ('educational', 'Learning'),
    ('set in the real world', 'Real Life'),
    ('historical fiction', 'History'),
    ('fantasy', 'Fantasy'),
    ('science fiction', 'Sci-Fi'),
    ('mystery', 'Mystery'),
    ('scary', 'Spooky'),
    ]
tone_choices = [
    ('humourous', 'Funny'),
    ('whimsical', 'Silly'),
    ('serious', 'Serious'),
    ('dramatic', 'Dramatic'),
    ('like a TED talk', 'Educational'),
    ('very descriptive and artistic', 'Engaging'),
    ]
temporal_choices = [
    ('in the past', 'Past'),
    ('in the present', 'Present'),
    ('in the future', 'Future'),
    ]
role_choices = [
    ('protagonist', 'Main Character'),
    ('antagonist', 'Main Bad Character'),
    ('friend of a main character', 'Friend'),
    ('family member of a main character', 'Family'),
    ('main supporting character', 'Sidekick'),
    ('member of a team', 'Team Member'),
    ('advisor to a main or supporting character', 'Mentor'),
    ('side character not affiliated with any other character or group', 'Random Side Character'),
    ('character that is not integral to the story line', 'NPC'),
    ]
use_choices = [
    ('private space', 'Private'),
    ('public space', 'Public'),
]
private_choices = [
    ('single family home', 'House'),
    ('multi-family building', 'Apartment'),
    ('very large family property', 'Estate'),
    ('a farm or farm house', 'Farm'),
    ('a ranch or ranch house', 'Ranch'),
    ('a castle or castle like structure', 'Castle'),
    ('a small home like a cottage', 'Cottage'),
    ('a small cabin', 'Cabin'),
    ('a treehouse or fort structure', 'Treehouse'),
    ('a private camp or camp ground area', 'Camp'),
    ('a private prison or jail', 'Prison'),
    ('a private military base or fort', 'Military Base'),
    ('a private research facility or lab', 'Lab'),
]
public_choices = [
    ('a park or public space', 'Park'),
    ('a playground', 'Playground'),
    ('a private art gallery or museum', 'Gallery'),
    ('a private library or book store', 'Library'),
    ('a hotel or motel', 'Hotel'),
    ('a resort or vacation destination', 'Resort'),
    ('a private/ public school or academy', 'School'),
    ('a private hospital or clinic', 'Hospital'),
    ('a neighborhood or city street', 'Street'),
    ('a pool or water park', 'Pool'),
    ('a sports field or stadium', 'Sports Field'),
    ('an open field', 'Field'),
    ('a stadium or arena', 'Stadium'),
    ('a central plaza or town square', 'Plaza'),
    ('a lake or body of water', 'Lake'),
    ('a beach', 'Beach'),
    ('a forest', 'Forest'),
    ('a desert', 'Desert'),
    ('a mountain', 'Mountain'),
    ('a cave', 'Cave'),
    ('a volcano', 'Volcano'),
]
general_location_choices = [
    ('on or near a beach', 'Coastal'),
    ('interior grassy plains', 'Plains'),
    ('on or near mountains', 'Mountainous'),
    ('in or next to a forest', 'Forest'),
    ('dessert', 'Dessert'),
]
specific_location_choices = [
    ('in a big city', 'City'),
    ('in a small town', 'Town'),
    ('in a rural area', 'Rural'),
    ('in a suburban area', 'Suburban'),
    ('in a small village', 'Village'),
    ('in a large village', 'Large Village'),
    ('away from any large cities', 'Remote'),
    ('hidden', 'Hidden'),
]
weather_choices = [
    ('mild most of the time', 'Temperate'),
    ('very little to no rain', 'Dry'),
    ('rains all the time', 'Rainy'),
    ('snows all the time', 'Snowy'),
    ('very cold all the time', 'Cold'),
    ('very hot all the time', 'Hot'),
    ('hot and humid', 'Tropical'),
    ('cold and dry', 'Polar'),
]
class Adventure(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='adventures'
    )
    adventure_number = models.IntegerField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    # Store all data in JSON fields
    style_data = JSONField(default=dict)
    world_data = JSONField(default=dict)
    character_data = JSONField(default=list)
    setting_data = JSONField(default=list)

    class Meta:
        unique_together = ['user', 'adventure_number']

    def __str__(self):
        return f"{self.user.username}'s Adventure {self.adventure_number}"

    @property
    def character_limit(self):
        """Return character limit based on number of stories"""
        if not self.pk:  # If this is a new instance (not saved yet)
            return 5
        story_count = self.stories.count()
        return 7 if story_count > 0 else 5

    @property
    def setting_limit(self):
        """Return setting limit based on number of stories"""
        if not self.pk:  # If this is a new instance (not saved yet)
            return 5
        story_count = self.stories.count()
        return 7 if story_count > 0 else 5

    def append_world_data(self, new_data):
        """Append new world data to existing data"""
        for key, value in new_data.items():
            if key in self.world_data:
                # For text fields, append with a separator
                if isinstance(value, str) and isinstance(self.world_data[key], str):
                    self.world_data[key] = f"{self.world_data[key]}\n\n{value}"
                # For lists or other structures, extend/update as needed
                elif isinstance(value, list):
                    self.world_data[key].extend(value)
                elif isinstance(value, dict):
                    self.world_data[key].update(value)
            else:
                self.world_data[key] = value

    def add_character(self, character_data):
        """Add a new character if within limits"""
        current_characters = self.character_data
        if len(current_characters) >= self.character_limit:
            raise ValidationError(f"Cannot add more characters. Limit is {self.character_limit}.")
        
        # Validate character data structure
        required_fields = {'about'}
        if not all(field in character_data for field in required_fields):
            raise ValidationError("Missing required character fields")
        
        self.character_data.append(character_data)
        return True

    def add_setting(self, setting_data):
        """Add a new setting if within limits"""
        current_settings = self.setting_data
        if len(current_settings) >= self.setting_limit:
            raise ValidationError(f"Cannot add more settings. Limit is {self.setting_limit}.")
        
        # Update required fields to match new structure
        required_fields = {
            'about'
        }
        if not all(field in setting_data for field in required_fields):
            raise ValidationError("Missing required setting fields")
        
        self.setting_data.append(setting_data)
        return True

    def update_character(self, index, character_data):
        """Update an existing character"""
        if index >= len(self.character_data):
            raise ValidationError("Character index out of range")
        
        # Validate character data structure
        required_fields = {'name', 'role', 'gender', 'age', 'species', 'description', 'about'}
        if not all(field in character_data for field in required_fields):
            raise ValidationError("Missing required character fields")
        
        self.character_data[index].update(character_data)
        return True

    def update_setting(self, index, setting_data):
        """Update an existing setting"""
        if index >= len(self.setting_data):
            raise ValidationError("Setting index out of range")
        
        # Update required fields to match new structure
        required_fields = {
           'about'
        }
        if not all(field in setting_data for field in required_fields):
            raise ValidationError("Missing required setting fields")
        
        self.setting_data[index].update(setting_data)
        return True

    def clean(self):
        """Validate the model data"""
        super().clean()
        
        # Only validate counts, not content
        if len(self.character_data) > self.character_limit:
            raise ValidationError(f"Too many characters. Limit is {self.character_limit}")
        
        if len(self.setting_data) > self.setting_limit:
            raise ValidationError(f"Too many settings. Limit is {self.setting_limit}")

    def save(self, *args, **kwargs):
        """Override save to ensure validation"""
        self.clean()
        super().save(*args, **kwargs)

class Style(models.Model):
    adventure = models.OneToOneField(Adventure, on_delete=models.CASCADE, related_name='style')
    age_group = models.CharField(max_length=100, choices=age_group_choices)
    gender = models.CharField(max_length=100, choices=style_gender_choices)
    genre = models.CharField(max_length=100, choices=genre_choices)
    tone = models.CharField(max_length=100, choices=tone_choices)
    #style = models.CharField(max_length=100, choices=style_choices)
    #read_time = models.CharField(max_length=100, choices=read_time_choices)

    def __str__(self):
        return f"Style for {self.adventure}"

class World(models.Model):
    adventure = models.OneToOneField(Adventure, on_delete=models.CASCADE, related_name='world')
    name = models.CharField(max_length=100, blank=True)
    temporal = models.CharField(max_length=100, choices=temporal_choices)
    general = models.TextField()
    backstory = models.TextField()
    current_events = models.TextField()

    def __str__(self):
        return f"World for {self.adventure}"

class Character(models.Model):
    adventure = models.ForeignKey(Adventure, on_delete=models.CASCADE, related_name='characters')
    name = models.CharField(max_length=255)
    gender = models.CharField(max_length=100, choices=character_gender_choices)
    age = models.IntegerField()
    species = models.CharField(max_length=255)
    role = models.CharField(max_length=100, choices=role_choices)
    description = models.TextField()
    about = models.TextField()
    order = models.PositiveIntegerField(default=0)  # To maintain character order

    class Meta:
        ordering = ['order']

    def __str__(self):
        return f"{self.name} - {self.adventure}"

class Setting(models.Model):
    adventure = models.ForeignKey(Adventure, on_delete=models.CASCADE, related_name='settings')
    use_type = models.CharField(max_length=100, choices=use_choices)
    private_space_type = models.CharField(max_length=100, choices=private_choices, blank=True)
    public_space_type = models.CharField(max_length=100, choices=public_choices, blank=True)
    general_location = models.CharField(max_length=100, choices=general_location_choices, blank=True)
    specific_location = models.CharField(max_length=100, choices=specific_location_choices, blank=True)
    weather = models.CharField(max_length=100, choices=weather_choices, blank=True)
    name = models.CharField(max_length=100, blank=True)
    about = models.TextField()
    order = models.PositiveIntegerField(default=0)  # To maintain setting order

    class Meta:
        ordering = ['order']

    def __str__(self):
        return f"Setting {self.order + 1} for {self.adventure}"
    
class Story(models.Model):
    adventure = models.ForeignKey(Adventure, on_delete=models.CASCADE, related_name='stories')
    prompt = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    # Fields to be populated by the backend process
    outline = models.TextField(blank=True)
    title = models.CharField(max_length=255, blank=True)

    summary = models.TextField(blank=True, null=True)
    input_token_count = models.IntegerField(default=0, null=True)
    output_token_count = models.IntegerField(default=0, null=True)
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('processing', 'Processing'),
        ('completed', 'Completed'),
        ('failed', 'Failed')
    ]
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    error = models.TextField(blank=True)
    audio = models.FileField(upload_to='story_audio/', null=True, blank=True)
    audio_voice = models.CharField(max_length=100, null=True, blank=True)

    def __str__(self):
        return f"Story for {self.adventure} - {self.created_at.strftime('%Y-%m-%d %H:%M')}"

    class Meta:
        verbose_name_plural = "Stories"

class StoryImages(models.Model):
    story = models.OneToOneField(Story, on_delete=models.CASCADE, related_name='story_images')
    cover_image = models.ImageField(upload_to='story_images/', null=True, blank=True)

    def __str__(self):
        return f"Images for Story {self.story.id}"

class ChapterImage(models.Model):
    story_images = models.ForeignKey(StoryImages, on_delete=models.CASCADE, related_name='chapter_images')
    part_key = models.CharField(max_length=20)
    chapter_key = models.CharField(max_length=20)
    image = models.ImageField(upload_to='chapter_images/')
    text_marker = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('story_images', 'part_key', 'chapter_key')
        ordering = ['part_key', 'chapter_key']

    def __str__(self):
        return f"{self.story_images.story.id} - {self.part_key} - {self.chapter_key}"

class StoryContent(models.Model):
    story = models.OneToOneField(Story, on_delete=models.CASCADE, related_name='content')
    raw_content = JSONField(default=dict)  # Will store {part1: {chapter1: {full_text: str, summary: str}}}

    def __str__(self):
        return f"Content for Story {self.story.id}"

    class Meta:
        verbose_name = "Story Content"
        verbose_name_plural = "Story Contents"