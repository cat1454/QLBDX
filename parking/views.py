from django.http import StreamingHttpResponse, JsonResponse, HttpResponse
from django.shortcuts import render, redirect
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.decorators import login_required
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User, Group
from django.contrib import messages
from django.db import transaction
from django.urls import reverse
from django.core.exceptions import ValidationError
from django.core.files.storage import default_storage
from django.conf import settings

from datetime import datetime
from collections import deque
import threading
import time
import os
import json
import uuid

from .forms import CustomUserCreationForm, LoginForm, ProfileUpdateForm, UserUpdateForm
from .models import Profile

# ==========================================================
# STREAM MANAGEMENT (Raspberry Pi camera)
# ==========================================================

streams = {}                    # src -> latest jpeg frame (bytes)
stream_locks = {}               # src -> threading.Lock()
stream_lock_global = threading.Lock()  # bảo vệ dict streams & stream_locks

# History nhận diện biển số (thread-safe)
detection_history = deque(maxlen=200)
history_lock = threading.Lock()

# Giới hạn kích thước frame & ảnh upload
MAX_FRAME_SIZE = 1024 * 1024  # 1MB
MAX_UPLOAD_SIZE = 5 * 1024 * 1024  # 5MB


def get_stream_frame(src):
    with stream_lock_global:
        if src in streams:
            with stream_locks[src]:
                return streams[src]
    return None


def gen_mjpeg(src):
    boundary = b'--frame\r\n'
    while True:
        frame = get_stream_frame(src)
        if frame:
            yield boundary + b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n'
        else:
            time.sleep(0.05)


@csrf_exempt
def receive_stream(request, src):
    """Raspberry Pi POST frame JPEG liên tục"""
    if request.method != 'POST':
        return HttpResponse("Only POST allowed", status=405)

    if len(request.body) > MAX_FRAME_SIZE:
        return HttpResponse("Frame too large", status=413)

    with stream_lock_global:
        if src not in stream_locks:
            stream_locks[src] = threading.Lock()
        with stream_locks[src]:
            streams[src] = request.body

    return HttpResponse("OK", status=200)


@login_required
def video_feed(request, src):
    return StreamingHttpResponse(
        gen_mjpeg(src),
        content_type='multipart/x-mixed-replace; boundary=frame'
    )

# ==========================================================
# BIỂN SỐ & NHẬN DIỆN
# ==========================================================

@csrf_exempt
def upload_license_plate(request):
    """Raspberry Pi gửi ảnh + thông tin biển số"""
    if request.method != "POST":
        return JsonResponse({"status": "error", "msg": "Invalid method"})

    try:
        plate = request.POST.get("plate", "").strip()
        confidence = request.POST.get("confidence", "")
        source = request.POST.get("source", "")
        image_file = request.FILES.get("image")

        if not image_file:
            return JsonResponse({"status": "error", "msg": "No image received"})

        if image_file.size > MAX_UPLOAD_SIZE:
            return JsonResponse({"status": "error", "msg": "Image too large"})

        # Tạo tên file unique
        ext = os.path.splitext(image_file.name)[1]
        filename = f"uploads/plate_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex}{ext}"
        filepath = default_storage.save(filename, image_file)
        full_path = default_storage.path(filepath)

        # Lưu vào history (thread-safe)
        record = {
            "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "plate": plate,
            "conf": confidence,
            "src": source,
            "path": filepath
        }

        with history_lock:
            # Nếu deque đầy -> xóa file cũ
            if len(detection_history) == detection_history.maxlen:
                old = detection_history[0]
                if default_storage.exists(old["path"]):
                    default_storage.delete(old["path"])
            detection_history.append(record)

        print(f"Received plate {plate} from {source} ({confidence}%) -> {filepath}")

        return JsonResponse({
            "status": "ok",
            "plate": plate,
            "confidence": confidence,
            "file": f"/media/{filepath}"
        })

    except Exception as e:
        return JsonResponse({"status": "error", "msg": str(e)})


@login_required
def latest_detections(request):
    """API cho dashboard lấy lịch sử nhận diện"""
    with history_lock:
        history_list = list(detection_history)
        latest = history_list[-1] if history_list else None

    return JsonResponse({
        "latest": latest,
        "history": history_list,
        "total": len(history_list)
    })


@login_required
def get_parking_status(request):
    """Trạng thái bãi xe (có thể mở rộng kết nối DB sau)"""
    status = {
        str(i): {"occupied": False, "plate": None, "entry_time": None}
        for i in range(1, 7)
    }
    occupied = sum(1 for v in status.values() if v["occupied"])
    return JsonResponse({
        "status": status,
        "total_spots": 6,
        "occupied_spots": occupied
    })


@csrf_exempt
@login_required
def toggle_barrier(request):
    if request.method == 'POST':
        # TODO: Gửi lệnh GPIO hoặc MQTT tới barrier
        return JsonResponse({"status": "ok", "message": "Barrier toggled"})
    return JsonResponse({"status": "error", "message": "Method not allowed"}, status=405)


# ==========================================================
# AUTH & USER MANAGEMENT
# ==========================================================

def home(request):
    context = {
        'available_slots': 12,
        'total_slots': 20,
        'price_per_hour': 10000
    }
    return render(request, 'parking/home.html', context)


def login_view(request):
    if request.user.is_authenticated:
        return redirect_to_dashboard(request.user)

    form = LoginForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        username = form.cleaned_data['username']
        password = form.cleaned_data['password']
        remember = form.cleaned_data.get('remember', False)

        user = authenticate(request, username=username, password=password)
        if user and user.is_active:
            login(request, user)
            if not remember:
                request.session.set_expiry(0)
            return redirect_to_dashboard(user)

        messages.error(request, 'Tên đăng nhập hoặc mật khẩu không đúng.')

    return render(request, 'parking/login.html', {'form': form})


def redirect_to_dashboard(user):
    profile = getattr(user, "profile", None)
    if profile and profile.role == "Admin":
        return redirect('dashboard_admin')
    elif profile and profile.role == "User":
        return redirect('dashboard_user')
    else:
        return redirect('dashboard_customer')


def register_view(request):
    if request.user.is_authenticated:
        return redirect('home')

    if request.method == 'POST':
        form = CustomUserCreationForm(request.POST)
        try:
            with transaction.atomic():
                if form.is_valid():
                    user = form.save(commit=False)
                    user.email = form.cleaned_data['email']
                    user.save()

                    role = request.POST.get('role', 'Customer')
                    profile = Profile.objects.create(user=user, role=role)
                    group, _ = Group.objects.get_or_create(name=role)
                    user.groups.add(group)
                    login(request, user)

                    return JsonResponse({
                        'success': True,
                        'redirect': reverse('dashboard_customer' if role == 'Customer' else 'dashboard_user'),
                        'message': 'Đăng ký thành công'
                    })
                else:
                    return JsonResponse({'success': False, 'errors': form.errors})
        except Exception as e:
            return JsonResponse({'success': False, 'message': str(e)})
    else:
        form = CustomUserCreationForm()
    return render(request, 'parking/register.html', {'form': form})


@login_required
def logout_view(request):
    logout(request)
    messages.success(request, 'Đã đăng xuất.')
    return redirect('login')


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
    profile, _ = Profile.objects.get_or_create(user=request.user, defaults={'role': 'Customer', 'wallet': 0})
    transactions = getattr(profile, 'transaction_set', None)
    recent_tx = transactions.order_by('-timestamp')[:5] if transactions else []
    return render(request, 'parking/profile.html', {
        'profile': profile,
        'transactions': recent_tx
    })


@login_required(login_url='login')
def edit_profile(request):
    profile = Profile.objects.get_or_create(user=request.user)[0]
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


@login_required
def parking_history(request):
    return render(request, 'parking/parking_history.html')


def test_connection(request):
    return HttpResponse("django-server-ok")