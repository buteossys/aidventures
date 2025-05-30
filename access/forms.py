from django import forms
from django.contrib.auth.models import User
from django.core.validators import EmailValidator, RegexValidator
from user_profile.models import UserProfile  # Import the existing UserProfile model
from access.models import ContactModel
from django.contrib.auth.password_validation import validate_password
from phonenumber_field.formfields import PhoneNumberField
from phonenumber_field.widgets import PhoneNumberPrefixWidget
from django.forms.widgets import Select, TextInput
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError

User = get_user_model()

class RegistrationForm(forms.Form):
    
    name = forms.CharField(
        max_length=20,
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )
    username = forms.CharField(
        max_length=20,
        widget=forms.TextInput(attrs={'class': 'form-control', 'required': True})
    )
    email = forms.EmailField(
        widget=forms.EmailInput(attrs={'class': 'form-control', 'required': True}),
        validators=[EmailValidator()]
    )
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'required': True}),
        validators=[validate_password]
    )
    confirm_password = forms.CharField(
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'required': True})
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def clean_password(self):
        """Validate password before any other validations"""
        password = self.cleaned_data.get('password')
        try:
            validate_password(password)
        except ValidationError as e:
            raise forms.ValidationError(e.messages)
        return password

    def clean_email(self):
        """Validate email uniqueness"""
        email = self.cleaned_data.get('email')
        if email and User.objects.filter(email=email).exists():
            raise forms.ValidationError("Email already registered")
        return email

    def clean_username(self):
        """Validate username uniqueness"""
        username = self.cleaned_data.get('username')
        if username and User.objects.filter(username=username).exists():
            raise forms.ValidationError("Username already registered")
        return username

    def clean(self):
        """Final validation for password match"""
        cleaned_data = super().clean()
        password = cleaned_data.get('password')
        confirm_password = cleaned_data.get('confirm_password')
        
        if password and confirm_password and password != confirm_password:
            raise forms.ValidationError("Passwords do not match")
        
        return cleaned_data

class ContactForm(forms.ModelForm):
    class Meta:
        model = ContactModel
        fields = [
            'name',
            'sender', 
            'message', 
            'cc_myself',
        ] 

        def clean_name(self):
            name = self.cleaned_data['name']
            # You can add custom validation logic here
            if not name.isalpha():
                raise forms.ValidationError("Name should only contain letters.")
            return name

        def clean(self):
            cleaned_data = super().clean()
            name = cleaned_data.get('name')
            message = cleaned_data.get('message')

            if name and message and "bad word" in message.lower():
                raise forms.ValidationError("Your message contains inappropriate content.")
            return cleaned_data

class LoginForm(forms.Form):
    email = forms.EmailField(
        widget=forms.EmailInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter your email'
        })
    )
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter your password'
        })
    )

class ForgotPasswordForm(forms.Form):
    email = forms.EmailField(
        widget=forms.EmailInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter your email address'
        })
    )

class ResetPasswordForm(forms.Form):
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter new password'
        }),
        min_length=8
    )
    confirm_password = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Confirm new password'
        })
    )

    def clean(self):
        cleaned_data = super().clean()
        password = cleaned_data.get('password')
        confirm_password = cleaned_data.get('confirm_password')

        if password and confirm_password and password != confirm_password:
            raise forms.ValidationError("Passwords do not match")
        return cleaned_data