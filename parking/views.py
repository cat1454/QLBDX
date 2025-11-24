from django.http import StreamingHttpResponse, JsonResponse, HttpResponse
from django.shortcuts import render, redirect
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.decorators import login_required
from django.urls import reverse
from django.utils import timezone
from datetime import datetime
from collections import deque
from decimal import Decimal
import threading
import json
import cv2
import numpy as np
import math

# Global variables for stream handling
streams = {}
stream_locks = {}
detection_history = deque(maxlen=200)  # Keep last 200 detections

def get_stream_frame(camera_id):
    """Get the latest frame from a specific camera stream (from file)"""
    import os
    import time
    
    frame_path = f'media/streams/{camera_id}.jpg'
    
    # Kiểm tra file tồn tại và còn mới (dưới 10 giây)
    if os.path.exists(frame_path):
        file_age = time.time() - os.path.getmtime(frame_path)
        if file_age > 10:
            print(f"⚠️ Stream file too old ({file_age:.1f}s) for {camera_id}")
            return None
            
        try:
            # Đọc file với retry nếu bị lock
            for _ in range(3):  # Thử 3 lần
                try:
                    with open(frame_path, 'rb') as f:
                        return f.read()
                except (IOError, OSError):
                    time.sleep(0.01)  # Đợi 10ms rồi thử lại
        except Exception as e:
            print(f"❌ Error reading frame: {e}")
    return None

def gen_frames(camera_id):
    """Generator for video stream frames - liên tục stream với error handling"""
    import time
    last_frame = None  # Giữ frame cuối cùng
    
    while True:
        try:
            frame = get_stream_frame(camera_id)
            if frame is not None:
                last_frame = frame  # Cập nhật frame mới nhất
                yield (b'--frame\r\nContent-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')
            elif last_frame is not None:
                # Nếu không có frame mới, hiển thị lại frame cũ
                yield (b'--frame\r\nContent-Type: image/jpeg\r\n\r\n' + last_frame + b'\r\n')
            else:
                # Nếu chưa có frame nào, yield empty frame để giữ connection
                time.sleep(0.1)
                continue
            
            time.sleep(0.033)  # ~30 FPS (1/30 = 0.033s)
        except GeneratorExit:
            # Client đóng connection - exit gracefully
            print(f"Stream closed for camera: {camera_id}")
            break
        except Exception as e:
            # Log lỗi nhưng không dừng generator
            print(f"Error in gen_frames for {camera_id}: {e}")
            time.sleep(0.1)
            continue

@login_required
def video_feed(request, src):
    """View for video stream với keep-alive headers"""
    response = StreamingHttpResponse(
        gen_frames(src),
        content_type='multipart/x-mixed-replace; boundary=frame'
    )
    # Thêm headers để giữ connection
    response['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    response['Pragma'] = 'no-cache'
    response['Expires'] = '0'
    response['X-Accel-Buffering'] = 'no'  # Disable nginx buffering nếu có
    return response

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
    """API endpoint for getting latest detections from DATABASE"""
    try:
        from .models import VehicleDetection
        from django.utils import timezone as tz
        
        # Lấy 20 detection mới nhất từ database
        detections = VehicleDetection.objects.all().order_by('-detected_at')[:20]
        
        latest = None
        if detections:
            latest_det = detections[0]
            # Convert UTC sang giờ local (Asia/Ho_Chi_Minh)
            local_time = tz.localtime(latest_det.detected_at)
            latest = {
                "time": local_time.strftime("%Y-%m-%d %H:%M:%S"),
                "plate": latest_det.license_plate,
                "conf": f"{latest_det.confidence:.2%}",
                "path": latest_det.image_path.name if latest_det.image_path else None,
                "event": latest_det.event_type
            }
        
        history = [{
            "time": tz.localtime(det.detected_at).strftime("%Y-%m-%d %H:%M:%S"),
            "plate": det.license_plate,
            "conf": f"{det.confidence:.2%}",
            "path": det.image_path.name if det.image_path else None,
            "event": det.event_type
        } for det in detections]
        
        return JsonResponse({
            'success': True,
            'latest': latest,
            'history': history
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': str(e)
        }, status=500)

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
            
            # Chuyển hướng dựa trên vai trò (superuser = Admin)
            if user.is_superuser:
                return redirect('dashboard_admin')
            else:
                return redirect('dashboard_user')
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
def add_staff(request):
    """Admin-only view to create new staff accounts"""
    # Check if user is admin (superuser)
    if not request.user.is_superuser:
        messages.error(request, 'Bạn không có quyền thực hiện thao tác này.')
        return redirect('dashboard_user')
    
    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        email = request.POST.get('email', '').strip()
        password = request.POST.get('password', '').strip()
        full_name = request.POST.get('full_name', '').strip()
        
        # Validate inputs
        if not username or not password:
            messages.error(request, 'Tên đăng nhập và mật khẩu là bắt buộc.')
            return redirect('dashboard_admin')
        
        # Check if username already exists
        if User.objects.filter(username=username).exists():
            messages.error(request, f'Tên đăng nhập "{username}" đã tồn tại.')
            return redirect('dashboard_admin')
        
        # Check if email already exists (if provided)
        if email and User.objects.filter(email=email).exists():
            messages.error(request, f'Email "{email}" đã được sử dụng.')
            return redirect('dashboard_admin')
        
        try:
            # Create user (staff, not superuser)
            user = User.objects.create_user(
                username=username,
                email=email,
                password=password
            )
            
            # Set first_name if full_name provided
            if full_name:
                user.first_name = full_name
                user.save()
            
            messages.success(request, f'Đã tạo tài khoản nhân viên "{username}" thành công.')
        except Exception as e:
            messages.error(request, f'Lỗi khi tạo tài khoản: {str(e)}')
        
        return redirect('dashboard_admin')
    
    # GET request - redirect to admin dashboard
    return redirect('dashboard_admin')


@login_required(login_url='login')
def dashboard_user(request):
    return render(request, 'parking/dashboard_user.html', {'user': request.user})

@login_required
def payment_cashier(request):
    return render(request, 'parking/payment_cashier.html', {'user': request.user})


    
import os

from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile

@csrf_exempt
def upload_license_plate(request):
    """Nhận dữ liệu từ Raspberry Pi: ảnh + thông tin biển số (TỰ ĐỘNG ENTRY/EXIT)"""
    if request.method == "POST":
        try:
            from .models import VehicleDetection, ParkingSession
            from django.core.files.storage import default_storage
            
            plate = request.POST.get("plate", "").strip().upper()
            confidence_str = request.POST.get("confidence", "0")
            source = request.POST.get("source", "raspberrypi_cam")
            image_file = request.FILES.get("image")

            if not plate:
                return JsonResponse({"status": "error", "msg": "No plate received"})

            # Chuyển đổi confidence (có thể là "0.89" hoặc "0.89%")
            try:
                confidence = float(confidence_str.strip('%')) / 100 if '%' in confidence_str else float(confidence_str)
            except:
                confidence = 0.0

            # ⭐ KIỂM TRA BÃI ĐẦY - Đếm số xe đang đỗ (ACTIVE sessions)
            MAX_PARKING_SLOTS = 4  # Tổng số chỗ đỗ
            current_parked = ParkingSession.objects.filter(status='ACTIVE').count()
            
            # ⭐ TỰ ĐỘNG XÁC ĐỊNH EVENT TYPE (Lần 1 = ENTRY, Lần 2 = EXIT)
            active_session = ParkingSession.objects.filter(
                license_plate=plate,
                status='ACTIVE'
            ).first()
            
            if active_session:
                event_type = 'EXIT'
                message = f'🚗 Xe {plate} RA bãi'
            else:
                event_type = 'ENTRY'
                message = f'🚗 Xe {plate} VÀO bãi'
                
                # ⚠️ KIỂM TRA BÃI ĐẦY - CHỈ KHI XE VÀO
                if current_parked >= MAX_PARKING_SLOTS:
                    print(f"🔴 BÃI ĐẦY: {current_parked}/{MAX_PARKING_SLOTS} - Từ chối xe {plate}")
                    
                    # Lưu detection nhưng không tạo session
                    VehicleDetection.objects.create(
                        license_plate=plate,
                        confidence=confidence,
                        event_type='ENTRY',
                        camera_source=source,
                        image_path=image_file if image_file else None
                    )
                    
                    # Trả về 503 Service Unavailable để Raspberry Pi biết tạm dừng detect
                    return JsonResponse({
                        "status": "parking_full",
                        "msg": "Bãi đỗ xe đã đầy",
                        "plate": plate,
                        "available_slots": 0,
                        "total_slots": MAX_PARKING_SLOTS,
                        "action": "deny_entry",
                        "display_message": f"BÃI ĐẦY! Vui lòng quay lại sau"
                    }, status=503)

            # Lưu ảnh - Django ImageField sẽ tự động lưu vào media/detections/
            # ✅ LƯU VÀO DATABASE (VehicleDetection)
            detection = VehicleDetection.objects.create(
                license_plate=plate,
                confidence=confidence,
                event_type=event_type,
                camera_source=source,
                image_path=image_file if image_file else None  # Django tự động lưu file
            )
            
            # Lấy đường dẫn file đã lưu
            filename = detection.image_path.name if detection.image_path else None

            # ✅ XỬ LÝ PARKING SESSION
            response_data = {
                "status": "ok",
                "plate": plate,
                "confidence": f"{confidence:.2%}",
                "event_type": event_type,
                "message": message,
                "detection_id": detection.id,
                "file": filename,
                "available_slots": MAX_PARKING_SLOTS - current_parked,
                "total_slots": MAX_PARKING_SLOTS
            }

            if event_type == 'ENTRY':
                # Tạo phiên đỗ xe mới
                session = ParkingSession.objects.create(
                    license_plate=plate,
                    entry_time=timezone.now(),
                    entry_image=filename,
                    status='ACTIVE'
                )
                response_data['session_id'] = session.id
                response_data['action'] = 'open_barrier'
                print(f"✅ ENTRY: {plate} from {source} ({confidence:.2%}) -> Session #{session.id}")
                
            elif event_type == 'EXIT':
                # Kết thúc phiên đỗ xe - TỰ ĐỘNG TÍNH TOÁN
                active_session.complete_session(timezone.now(), filename)
                
                # Lấy chi tiết phí để trả về
                fee_breakdown = active_session.get_fee_breakdown()
                
                response_data['session_id'] = active_session.id
                response_data['duration_minutes'] = active_session.duration_minutes
                response_data['fee'] = int(active_session.fee)
                response_data['payment_status'] = active_session.payment_status
                response_data['fee_breakdown'] = fee_breakdown
                response_data['action'] = 'open_barrier'
                
                # Message thân thiện
                if active_session.fee == 0:
                    response_data['display_message'] = f"Cảm ơn! Miễn phí ({active_session.duration_minutes} phút)"
                else:
                    response_data['display_message'] = f"Phí đỗ xe: {int(active_session.fee):,}đ ({active_session.duration_minutes} phút)"
                
                print(f"✅ EXIT: {plate} from {source} ({confidence:.2%}) -> {active_session.duration_minutes}p, {active_session.fee:,.0f} VNĐ")

            return JsonResponse(response_data)

        except Exception as e:
            import traceback
            print(f"❌ Error in upload_license_plate: {str(e)}")
            print(traceback.format_exc())
            return JsonResponse({"status": "error", "msg": str(e)})

    return JsonResponse({"status": "error", "msg": "Invalid method"})

@csrf_exempt
def receive_stream(request, src):
    """Nhận stream từ Raspberry Pi (POST từng frame MJPEG) - Atomic write"""
    if request.method == 'POST':
        try:
            import os
            import shutil
            
            os.makedirs('media/streams', exist_ok=True)
            frame_path = f'media/streams/{src}.jpg'
            temp_path = f'media/streams/{src}.tmp'
            
            # Ghi vào file tạm trước
            with open(temp_path, 'wb') as f:
                f.write(request.body)
            
            # Sau đó move atomic (tránh đọc file đang ghi)
            shutil.move(temp_path, frame_path)
            
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
