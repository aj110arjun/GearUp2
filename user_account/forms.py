from django import forms
from django.contrib.auth.models import User
from django.core.validators import RegexValidator, MinLengthValidator
from django.core.files.images import get_image_dimensions
from django.core.exceptions import ValidationError

from .models import Profile


class ProfileEditForm(forms.ModelForm):
    name = forms.CharField(
        max_length=100,
        validators=[
            RegexValidator(
                regex=r'^[A-Za-z\s]+$',
                message='Name must contain only letters and spaces.'
            ),
            MinLengthValidator(3, message='Name must be at least 3 characters long.')
        ]
    )
    email = forms.EmailField(required=True)
    current_password = forms.CharField(widget=forms.PasswordInput(), required=False)
    new_password = forms.CharField(widget=forms.PasswordInput(), required=False)
    confirm_password = forms.CharField(widget=forms.PasswordInput(), required=False)

    class Meta:
        model = Profile
        fields = ['profile_image']  # Only profile-related fields here

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        if user:
            self.fields['name'].initial = user.get_full_name()
            self.fields['email'].initial = user.email
        self.user = user

    def clean_profile_image(self):
        image = self.cleaned_data.get('profile_image')
        if image:
            try:
                w, h = get_image_dimensions(image)
            except Exception:
                raise ValidationError("Uploaded file is not a valid image.")
        return image

    def save(self, commit=True):
        profile = super().save(commit=False)

        # Update User fields alongside Profile fields
        if self.user:
            self.user.first_name = self.cleaned_data.get('name', self.user.first_name)
            self.user.email = self.cleaned_data.get('email', self.user.email)
            if commit:
                self.user.save()
                profile.save()
        else:
            if commit:
                profile.save()
        return profile
