from django import forms
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Field, Submit, Fieldset
from django.forms import formset_factory
from .models import Adventure, Story, Style, World, Character, Setting
import logging

# Set up logger
logger = logging.getLogger('ganai')

class StyleForm(forms.ModelForm):
    class Meta:
        model = Style
        fields = [
            'age_group', 
            'gender', 
            'genre', 
            'tone'
        ]
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Make all style fields optional
        for field in self.fields:
            self.fields[field].required = False
        self.helper = FormHelper()
        self.helper.layout = Layout(
                    'age_group', 
                    'gender', 
                    'genre', 
                    'tone', 
            # Include form fields here
            Submit('continue_style', 'Continue')
        )
        self.helper.form_tag = False # Important for single-page form [cite: 18]

class WorldForm(forms.ModelForm):
    """Existing WorldForm modified to handle both new and append cases"""
    class Meta:
        model = World
        fields = [
            'name',
            'temporal',
            'general',
            'backstory',
            'current_events',
        ]

    def __init__(self, *args, adventure=None, source=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.adventure = adventure
        self.source = source
        
        # Make all world fields optional
        for field in self.fields:
            self.fields[field].required = False
        
        # Make all fields optional when in library mode
        if source == 'library':
            self.fields['name'].widget.attrs['placeholder'] = 'Name your adventure world...'
            self.fields['temporal'].widget.attrs['readonly'] = True
            # Change placeholders for append mode
            self.fields['general'].widget.attrs['placeholder'] = 'Add to existing description...'
            self.fields['backstory'].widget.attrs['placeholder'] = 'Add to existing backstory...'
            self.fields['current_events'].widget.attrs['placeholder'] = 'Add new current events...'
        
        self.helper = FormHelper()
        self.helper.layout = Layout(
            'name',
            'temporal',
            'general',
            'backstory',
            'current_events',
            Submit('back_world', 'Back'),
            Submit('continue_world', 'Save Changes' if source == 'library' else 'Continue')
        )
        self.helper.form_tag = False

    def save(self, commit=True):
        if self.source == 'library' and self.adventure:
            # Get or create the World instance
            world_instance, created = World.objects.get_or_create(adventure=self.adventure)
            new_data = self.cleaned_data
            
            # Replace text fields with new values
            for field in ['general', 'backstory', 'current_events']:
                if new_data.get(field):
                    # Update World model instance with new value
                    setattr(world_instance, field, new_data[field])
                    
                    # Update adventure's world_data with new value
                    self.adventure.world_data[field] = new_data[field]
            
            if commit:
                world_instance.save()
                self.adventure.save()  # Update adventure.updated_at
            return world_instance
        else:
            # Normal creation mode
            return super().save(commit)

    def has_changed(self):
        """Override has_changed to check if any non-empty data was submitted"""
        if not hasattr(self, 'cleaned_data'):
            return False
        
        # Check if any field has non-empty data
        for field in ['general', 'backstory', 'current_events']:
            if self.cleaned_data.get(field):
                return True
        
        return False

class CharacterBaseForm(forms.ModelForm):
    """Existing CharacterBaseForm modified to handle increased limits"""
    class Meta:
        model = Character
        fields = [
            'name',
            'gender',
            'age',
            'species',
            'role',
            'description',
            'about',
        ]

    def __init__(self, *args, adventure=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.adventure = adventure
        # Make all fields optional except 'about' when adding a character
        for field in self.fields:
            self.fields[field].required = False
        
        # Only make about required if other fields are filled
        self.fields['about'].required = False
        # Add placeholders
        self.fields['name'].widget.attrs['placeholder'] = 'Enter character name'
        self.fields['age'].widget.attrs['placeholder'] = 'Enter age'
        self.fields['species'].widget.attrs['placeholder'] = 'e.g. Human, Dragon, etc.'
        self.fields['description'].widget.attrs['placeholder'] = 'Describe physical appearance'
        self.fields['about'].widget.attrs['placeholder'] = 'Share personality and background'

    def clean(self):
        cleaned_data = super().clean()
        # Get all fields except 'about'
        other_fields = {k: v for k, v in cleaned_data.items() if k != 'about'}
        
        # If ALL other fields are empty AND about is empty, require about
        if not any(other_fields.values()) and not cleaned_data.get('about'):
            raise forms.ValidationError({'about': 'About section is required when no other fields are filled'})
        return cleaned_data

# Modify the formset factory based on adventure status
def get_character_formset(adventure=None):
    max_num = 7 if adventure and adventure.stories.exists() else 5
    return formset_factory(CharacterBaseForm, 
                          extra=1, 
                          max_num=max_num,
                          validate_max=True)

class CharacterFormSetHelper(FormHelper):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.form_tag = False
        self.layout = Layout(
            Fieldset(
                'Character',
                'name',
                'gender',
                'age',
                'species',
                'role',
                'description',
                'about'
            ),
            Submit('back_character', 'Back'),
            Submit('continue_character', 'Continue')            
        )

class SettingBaseForm(forms.ModelForm):
    """Existing SettingBaseForm modified to handle increased limits"""
    class Meta:
        model = Setting
        fields = [
            'use_type',
            'private_space_type',
            'public_space_type',
            'general_location',
            'specific_location',
            'weather',
            'name',
            'about',
        ]
        widgets = {
                 'name': forms.TextInput(attrs={'class': 'form-group'})
             }

    def __init__(self, *args, adventure=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.adventure = adventure
        # Make all fields optional except 'about' when adding a setting
        for field in self.fields:
            self.fields[field].required = False
        
        # Only make about required if other fields are filled
        self.fields['about'].required = False

    def clean(self):
        cleaned_data = super().clean()
        # Get all fields except 'about'
        other_fields = {k: v for k, v in cleaned_data.items() if k != 'about'}
        
        # If ALL other fields are empty AND about is empty, require about
        if not any(other_fields.values()) and not cleaned_data.get('about'):
            raise forms.ValidationError({'about': 'About section is required when no other fields are filled'})
        return cleaned_data

# Modify the formset factory based on adventure status
def get_setting_formset(adventure=None):
    max_num = 7 if adventure and adventure.stories.exists() else 3
    return formset_factory(SettingBaseForm, 
                          extra=1, 
                          max_num=max_num,
                          validate_max=True)

class SettingFormSetHelper(FormHelper):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.form_tag = False
        self.layout = Layout(
            Fieldset(
                'Setting',
                'use_type',
                'private_space_type',
                'public_space_type',
                'general_location',
                'specific_location',
                'weather',
                'name',
                'about'
            ),
            Submit('back_setting', 'Back'),
            Submit('continue_setting', 'Continue')            
        )

class StoryPromptForm(forms.ModelForm):
    prompt = forms.CharField(
        widget=forms.Textarea(attrs={
            'rows': 4,
            'placeholder': "Describe what you'd like to happen in this story...",
            'class': 'form-group'
        }),
        required=True,
    )

    class Meta:
        model = Story
        fields = ['prompt']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['prompt'].label = "Story Prompt"

    def save(self, commit=True):
        story = super().save(commit=False)
        if commit:
            story.save()
        return story

class ReviewChoicesForm(forms.Form):
    """Form for handling the review choices page"""
    source = forms.CharField(widget=forms.HiddenInput)
    
    def __init__(self, *args, adventure=None, source=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.adventure = adventure
        if source:
            self.fields['source'].initial = source
            
        # Initialize nested forms based on source
        if source == 'library':
            self.world_form = WorldForm(adventure=adventure, source=source, 
                                      instance=adventure.world if adventure else None)
            self.character_formset = get_character_formset(adventure=adventure)()
            self.setting_formset = get_setting_formset(adventure=adventure)()

# In your CharacterBaseForm
description = forms.CharField(
    widget=forms.Textarea(attrs={'class': 'editable-field', 'value': ''}),
    required=False
)
about = forms.CharField(
    widget=forms.Textarea(attrs={'class': 'editable-field', 'value': ''}),
    required=False
)

# In your SettingBaseForm
about = forms.CharField(
    widget=forms.Textarea(attrs={'class': 'editable-field', 'value': ''}),
    required=False
)

