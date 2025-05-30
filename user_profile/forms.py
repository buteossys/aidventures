from django import forms
from django.contrib.auth.models import User
from django.core.validators import EmailValidator, RegexValidator
from .models import User

class ProfileEditForm(forms.Form):
    first_name = forms.CharField(
        label='First Name',
        max_length=20,
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )
    last_name = forms.CharField(
        label='Last Name',
        max_length=20,
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )
    username = forms.CharField(
        label='User Name',
        max_length=20,
        widget=forms.TextInput(attrs={'class': 'form-control', 'required': True})
    )
    email = forms.CharField(
        label='Email',
        widget=forms.EmailInput(attrs={'class': 'form-control', 'required': True}),
        validators=[EmailValidator(message='Enter a valid email address')]
    )

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        if self.user:
            self.fields['first_name'].initial = self.user.first_name
            self.fields['last_name'].initial = self.user.last_name
            self.fields['username'].initial = self.user.username
            self.fields['email'].initial = self.user.email
            

    def save(self):
        if self.user:
            self.user.first_name = self.cleaned_data['first_name']
            self.user.last_name = self.cleaned_data['last_name']
            self.user.username = self.cleaned_data['username']
            self.user.email = self.cleaned_data['email']
            self.user.save()
        return self.user
