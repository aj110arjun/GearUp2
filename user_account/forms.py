from django import forms
from django.contrib.auth.models import User

from .models import Profile

class ProfileEditForm(forms.ModelForm):
    name = forms.CharField(max_length=150, required=True)
    email = forms.EmailField(required=True)
    current_password = forms.CharField(widget=forms.PasswordInput(), required=False)
    new_password = forms.CharField(widget=forms.PasswordInput(), required=False)
    confirm_password = forms.CharField(widget=forms.PasswordInput(), required=False)

    class Meta:
        model = Profile
        fields = ['profile_image']

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        if user:
            self.fields['name'].initial = user.get_full_name()
            self.fields['email'].initial = user.email
