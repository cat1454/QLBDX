from django import forms
from django.contrib.auth.models import User
from .models import Profile

class UserUpdateForm(forms.ModelForm):
    email = forms.EmailField(required=True, label="Email")

    class Meta:
        model = User
        fields = ['email']


class ProfileUpdateForm(forms.ModelForm):
    class Meta:
        model = Profile
        fields = ['avatar', 'wallet']
        labels = {
            'avatar': 'Ảnh đại diện',
            'wallet': 'Số dư ví (VNĐ)'
        }
