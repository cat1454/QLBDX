from django.http import StreamingHttpResponse, JsonResponse, HttpResponse
from django.shortcuts import render, redirect
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.decorators import login_required
from django.urls import reverse
from datetime import datetime
from collections import deque
import threading
import json
import cv2
import numpy as np

# Global variables for stream handling
streams = {}
stream_locks = {}
detection_history = deque(maxlen=200)  # Keep last 200 detections

def get_stream_frame(camera_id):
    """Get the latest frame from a specific camera stream"""
    if camera_id in streams and streams[camera_id]:
        with stream_locks[camera_id]:
            return streams[camera_id]
    return None

def gen_frames(camera_id):
    """Generator for video stream frames"""
    while True:
        frame = get_stream_frame(camera_id)
        if frame is not None:
            yield (b'--frame\r\nContent-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')

@login_required
def video_feed(request, camera_id):
    """View for video stream"""
    return StreamingHttpResponse(
        gen_frames(camera_id),
        content_type='multipart/x-mixed-replace; boundary=frame'
    )

@csrf_exempt
def stream_upload(request):
    """API endpoint for receiving camera frames"""
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            camera_id = data.get('camera_id')
            frame_data = data.get('frame')
            
            if camera_id is None or frame_data is None:
                return JsonResponse({"status": "error", "message": "Missing camera_id or frame"}, status=400)

            # Initialize lock for new camera
            if camera_id not in stream_locks:
                stream_locks[camera_id] = threading.Lock()
            
            # Store frame
            with stream_locks[camera_id]:
                streams[camera_id] = frame_data.encode('utf-8')
            
            return JsonResponse({"status": "ok"})
        except json.JSONDecodeError:
            return JsonResponse({"status": "error", "message": "Invalid JSON"}, status=400)
        except Exception as e:
            return JsonResponse({"status": "error", "message": str(e)}, status=500)
            
    return JsonResponse({"status": "error", "message": "Method not allowed"}, status=405)

@login_required
def latest_detections(request):
    """API endpoint for getting latest detections"""
    latest = detection_history[-1] if detection_history else None
    return JsonResponse({
        "latest": latest,
        "history": list(detection_history)
    })

@csrf_exempt
@login_required
def upload_detection(request):
    """API endpoint for receiving license plate detections"""
    if request.method == 'POST':
        detection = {
            "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "plate": request.POST.get("plate", ""),
            "conf": request.POST.get("confidence", ""),
            "src": request.POST.get("source", "unknown")
        }
        
        if 'image' in request.FILES:
            # Handle image upload here
            pass
            
        detection_history.append(detection)
        return JsonResponse({"status": "ok"})
    return JsonResponse({"status": "error"}, status=405)

@login_required
def get_parking_status(request):
    """API endpoint for getting parking lot status"""
    # Implement your parking status logic here
    status = {
        str(i): {
            "occupied": False,
            "plate": None,
            "entry_time": None
        } for i in range(1, 7)
    }
    return JsonResponse({
        "status": status,
        "total_spots": 6,
        "occupied_spots": 0
    })

@csrf_exempt
@login_required
def toggle_barrier(request):
    """API endpoint for controlling the barrier"""
    if request.method == 'POST':
        # Implement your barrier control logic here
        return JsonResponse({
            "status": "ok",
            "message": "Đã điều khiển barrier"
        })
    return JsonResponse({"status": "error"}, status=405)

def test_connection(request):
    """Simple endpoint for testing server connection"""
    return HttpResponse("django-server"), redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User
from django.contrib import messages

from parking.form import ProfileUpdateForm, UserUpdateForm
from parking.models import Profile

def home(request):
    # Đảm bảo người dùng bắt đầu ở trạng thái đăng xuất khi vào trang home
    if request.user.is_authenticated:
        logout(request)
    
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
            
            # Chuyển hướng dựa trên vai trò
            if role == 'Admin':
                return redirect('dashboard_admin')
            elif role == 'User':
                return redirect('dashboard_user')
            elif role == 'Customer':
                return redirect('dashboard_customer')
            else:
                messages.error(request, 'Vai trò không hợp lệ!')
                return redirect('home')
        else:
            messages.error(request, 'Tên đăng nhập hoặc mật khẩu không đúng!')

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
    
import os

from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile

@csrf_exempt
def upload_license_plate(request):
    """Nhận dữ liệu từ Raspberry Pi: ảnh + thông tin biển số"""
    if request.method == "POST":
        try:
            plate = request.POST.get("plate", "")
            confidence = request.POST.get("confidence", "")
            source = request.POST.get("source", "")
            image_file = request.FILES.get("image")

            if not image_file:
                return JsonResponse({"status": "error", "msg": "No image received"})

            # Lưu ảnh vào thư mục media/uploads/
            filename = default_storage.save(f"uploads/{image_file.name}", image_file)

            # (Tùy chọn) lưu vào DB nếu có model LicensePlateLog
            # LicensePlateLog.objects.create(
            #     plate=plate, confidence=confidence, source=source, image=filename
            # )

            print(f"✅ Received {plate} from {source} ({confidence})")

            return JsonResponse({
                "status": "ok",
                "plate": plate,
                "confidence": confidence,
                "file": filename
            })

        except Exception as e:
            return JsonResponse({"status": "error", "msg": str(e)})

    return JsonResponse({"status": "error", "msg": "Invalid method"})

@csrf_exempt
def receive_stream(request, source_name):
    """Nhận stream từ Raspberry Pi (POST từng frame MJPEG)."""
    if request.method == 'POST':
        try:
            os.makedirs('media/streams', exist_ok=True)
            frame_path = f'media/streams/{source_name}.jpg'
            with open(frame_path, 'wb') as f:
                f.write(request.body)
            return HttpResponse("OK", status=200)
        except Exception as e:
            return HttpResponse(str(e), status=500)
    return HttpResponse("Only POST allowed", status=405)

from django.http import StreamingHttpResponse
from django.views.decorators import gzip

import os
import time


def parking_history(request):
    # render template lịch sử
    return render(request, 'parking/parking_history.html')

from django.shortcuts import render, redirect
from django.contrib.auth import login, authenticate, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db import transaction
from django.core.exceptions import ValidationError
from .form import CustomUserCreationForm, LoginForm
from .models import Profile
from django.contrib.auth.models import Group

def login_view(request):
    if request.user.is_authenticated:
        return redirect('home')
        
    if request.method == 'POST':
        form = LoginForm(request.POST)
        if form.is_valid():
            username = form.cleaned_data.get('username')
            password = form.cleaned_data.get('password')
            remember = form.cleaned_data.get('remember')
            
            try:
                user = authenticate(username=username, password=password)
                if user is not None:
                    if user.is_active:
                        login(request, user)
                        if not remember:
                            request.session.set_expiry(0)
                        
                        # Redirect based on role
                        profile = user.profile
                        if profile.role == 'Admin' or user.is_superuser:
                            return redirect('dashboard_admin')
                        elif profile.role == 'User':
                            return redirect('dashboard_user')
                        else:
                            return redirect('dashboard_customer')
                    else:
                        messages.error(request, 'Tài khoản đã bị vô hiệu hóa.')
                else:
                    messages.error(request, 'Tên đăng nhập hoặc mật khẩu không đúng.')
            except Exception as e:
                messages.error(request, f'Lỗi đăng nhập: {str(e)}')
    else:
        form = LoginForm()
    
    return render(request, 'parking/login.html', {'form': form})

def register_view(request):
    if request.user.is_authenticated:
        return JsonResponse({
            'success': False,
            'message': 'Bạn đã đăng nhập rồi'
        })
        
    if request.method == 'POST':
        form = CustomUserCreationForm(request.POST)
        try:
            with transaction.atomic():
                if form.is_valid():
                    user = form.save(commit=False)
                    user.email = form.cleaned_data['email']
                    user.save()

                    # Create profile
                    role = request.POST.get('role', 'Customer')
                    profile = Profile.objects.create(
                        user=user,
                        role=role
                    )

                    # Add to group
                    group, _ = Group.objects.get_or_create(name=role)
                    user.groups.add(group)

                    # Auto login after registration
                    login(request, user)
                    
                    # Return success response
                    return JsonResponse({
                        'success': True,
                        'redirect': reverse('dashboard_customer' if role == 'Customer' else 'home'),
                        'message': 'Đăng ký thành công'
                    })
                else:
                    return JsonResponse({
                        'success': False,
                        'message': 'Thông tin không hợp lệ. Vui lòng kiểm tra lại.',
                        'errors': form.errors
                    })
        except ValidationError as e:
            return JsonResponse({
                'success': False,
                'message': f'Lỗi xác thực: {e.message}'
            })
        except Exception as e:
            return JsonResponse({
                'success': False,
                'message': f'Lỗi đăng ký: {str(e)}'
            })
    else:
        return render(request, 'parking/register.html', {'form': CustomUserCreationForm()})

@login_required
def logout_view(request):
    logout(request)
    messages.success(request, 'Đã đăng xuất thành công.')
    return redirect('login')

@login_required
def profile_view(request):
    profile = request.user.profile
    context = {
        'profile': profile,
        'transactions': profile.transaction_set.order_by('-timestamp')[:5]
    }
    return render(request, 'parking/profile.html', context)