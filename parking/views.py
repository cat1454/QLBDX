from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User
from django.contrib import messages

from parking.form import ProfileUpdateForm, UserUpdateForm
from parking.models import Profile

def home(request):
    context = {
        'available_slots': 12,
        'total_slots': 20,
        'price_per_hour': 10000,
    }
    return render(request, 'parking/home.html', context)


def register_view(request):
    if request.method == 'POST':
        username = request.POST['username']
        email = request.POST['email']
        password1 = request.POST['password1']
        password2 = request.POST['password2']
        role = request.POST['role']

        # Kiểm tra hợp lệ
        if password1 != password2:
            messages.error(request, 'Mật khẩu không khớp!')
            return redirect('register')

        if User.objects.filter(username=username).exists():
            messages.error(request, 'Tên đăng nhập đã tồn tại!')
            return redirect('register')

        # Tạo user
        user = User.objects.create_user(username=username, email=email, password=password1)
        user.first_name = role  # lưu tạm role trong first_name (hoặc bạn có thể tạo model Profile riêng sau)
        user.save()

        messages.success(request, 'Đăng ký thành công! Vui lòng đăng nhập.')
        return redirect('login')

    return render(request, 'parking/register.html')


def login_view(request):
    if request.method == 'POST':
        username = request.POST['username']
        password = request.POST['password']
        user = authenticate(request, username=username, password=password)

        if user is not None:
            login(request, user)
            role = user.first_name  # lấy role đã lưu khi đăng ký

            # Chuyển hướng theo vai trò
            if role == 'Admin':
                return redirect('dashboard_admin')
            elif role == 'User':
                return redirect('dashboard_user')
            elif role == 'Customer':
                return redirect('dashboard_customer')
            else:
                messages.warning(request, 'Vai trò không hợp lệ!')
                return redirect('home')
        else:
            messages.error(request, 'Sai tên đăng nhập hoặc mật khẩu!')

    return render(request, 'parking/login.html')


def logout_view(request):
    logout(request)
    return redirect('home')
from django.contrib.auth.decorators import login_required

@login_required(login_url='login')
def dashboard_admin(request):
    return render(request, 'parking/dashboard_admin.html', {'user': request.user})


@login_required(login_url='login')
def dashboard_user(request):
    return render(request, 'parking/dashboard_user.html', {'user': request.user})


@login_required(login_url='login')
def dashboard_customer(request):
    return render(request, 'parking/dashboard_customer.html', {'user': request.user})
@login_required(login_url='login')
def profile_view(request):
    # Nếu user chưa có profile thì tự tạo mới
    profile, created = Profile.objects.get_or_create(
        user=request.user,
        defaults={
            'role': 'Customer',
            'wallet': 0
        }
    )
    return render(request, 'parking/profile.html', {'profile': profile})

# Cập nhật profile
@login_required(login_url='login')
def edit_profile(request):
    profile = request.user.profile

    if request.method == 'POST':
        user_form = UserUpdateForm(request.POST, instance=request.user)
        profile_form = ProfileUpdateForm(request.POST, request.FILES, instance=profile)
        
        if user_form.is_valid() and profile_form.is_valid():
            user_form.save()
            profile_form.save()
            messages.success(request, 'Cập nhật thông tin thành công!')
            return redirect('profile')
    else:
        user_form = UserUpdateForm(instance=request.user)
        profile_form = ProfileUpdateForm(instance=profile)

    return render(request, 'parking/edit_profile.html', {
        'user_form': user_form,
        'profile_form': profile_form,
    })