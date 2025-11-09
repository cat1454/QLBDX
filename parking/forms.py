from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from .models import Profile


# ============================================
# 🔹 Form Đăng ký người dùng mới
# ============================================
class CustomUserCreationForm(UserCreationForm):
    email = forms.EmailField(required=True, label="Email")
    role = forms.CharField(widget=forms.HiddenInput(), required=False)

    class Meta:
        model = User
        fields = ("username", "email", "password1", "password2")

    def clean_email(self):
        email = self.cleaned_data.get("email")
        if User.objects.filter(email=email).exists():
            raise forms.ValidationError("Email đã được sử dụng.")
        return email

    def clean_username(self):
        username = self.cleaned_data.get("username")
        if User.objects.filter(username=username).exists():
            raise forms.ValidationError("Tên đăng nhập đã tồn tại.")
        return username


# ============================================
# 🔹 Form Đăng nhập người dùng
# ============================================
class LoginForm(forms.Form):
    username = forms.CharField(
        max_length=150,
        label="Tên đăng nhập",
        widget=forms.TextInput(attrs={"placeholder": "Nhập tên đăng nhập"})
    )
    password = forms.CharField(
        label="Mật khẩu",
        widget=forms.PasswordInput(attrs={"placeholder": "Nhập mật khẩu"})
    )
    remember = forms.BooleanField(required=False, label="Ghi nhớ đăng nhập")


# ============================================
# 🔹 Form Cập nhật thông tin User (email, v.v.)
# ============================================
class UserUpdateForm(forms.ModelForm):
    email = forms.EmailField(required=True, label="Email")

    class Meta:
        model = User
        fields = ["email"]


# ============================================
# 🔹 Form Cập nhật hồ sơ Profile (avatar, ví)
# ============================================
class ProfileUpdateForm(forms.ModelForm):
    class Meta:
        model = Profile
        fields = ["avatar", "wallet"]
        labels = {
            "avatar": "Ảnh đại diện",
            "wallet": "Số dư ví (VNĐ)",
        }
