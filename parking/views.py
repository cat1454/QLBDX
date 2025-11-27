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

# ==================================================================================
# CAMERA STREAMING SYSTEM - Hệ thống stream camera từ Raspberry Pi
# ==================================================================================
# 
# KIẾN TRÚC:
# 1. Raspberry Pi --POST--> /api/stream/raspberrypi_cam (lưu frame vào file)
# 2. Browser --GET--> /video_feed/raspberrypi_cam (đọc file và stream MJPEG)
#
# FLOW:
#   Raspberry Pi                Django Server              Browser
#        |                            |                        |
#        |--POST frame.jpg----------->|                        |
#        |                      [Save to disk]                 |
#        |                            |<-------GET stream------|
#        |                      [Read from disk]               |
#        |                      [Generate MJPEG]               |
#        |                            |-------Frames---------->|
#        |--POST frame.jpg----------->|                        |
#        |                      [Update disk]                  |
#        |                      [Read new frame]               |
#        |                            |-------Frames---------->|
# ==================================================================================

# Global variables for stream handling
streams = {}
stream_locks = {}
detection_history = deque(maxlen=200)  # Keep last 200 detections

def get_stream_frame(camera_id):
    """
    📹 ĐỌC FRAME TỪ FILE - Được gọi ~30 lần/giây
    
    Mục đích: Đọc frame mới nhất từ file mà Raspberry Pi đã POST lên
    
    Args:
        camera_id (str): ID camera (vd: 'raspberrypi_cam')
    
    Returns:
        bytes: JPEG image data hoặc None nếu lỗi
    
    Logic:
        1. Kiểm tra file tồn tại
        2. Kiểm tra file age (< 10 giây = còn fresh)
        3. Đọc file với retry (phòng file đang được ghi)
        4. Return binary JPEG data
    """
    import os
    import time
    
    frame_path = f'media/streams/{camera_id}.jpg'
    
    # ✅ Step 1: Kiểm tra file tồn tại
    if not os.path.exists(frame_path):
        print(f"❌ Stream file NOT FOUND: {frame_path}")
        return None
    
    # ✅ Step 2: Kiểm tra file còn mới không (< 10 giây)
    file_age = time.time() - os.path.getmtime(frame_path)
    if file_age > 10:
        print(f"⚠️ Stream file too old ({file_age:.1f}s) for {camera_id}")
        return None
    
    # 📊 Logging (mỗi 30 lần đọc = 1 giây)
    if not hasattr(get_stream_frame, 'counter'):
        get_stream_frame.counter = {}
    if camera_id not in get_stream_frame.counter:
        get_stream_frame.counter[camera_id] = 0
    
    get_stream_frame.counter[camera_id] += 1
    if get_stream_frame.counter[camera_id] % 30 == 0:
        file_size = os.path.getsize(frame_path) / 1024
        print(f"📹 Reading frame for {camera_id}: age={file_age:.1f}s, size={file_size:.1f}KB")
    
    # ✅ Step 3: Đọc file với retry (tránh race condition khi Rasp đang ghi)
    try:
        for attempt in range(3):  # Thử 3 lần
            try:
                with open(frame_path, 'rb') as f:
                    frame_data = f.read()
                    if len(frame_data) > 0:
                        return frame_data  # ✅ Success!
                    else:
                        print(f"⚠️ Empty frame file for {camera_id}")
                        return None
            except (IOError, OSError) as e:
                if attempt == 2:  # Lần cuối cùng
                    print(f"❌ Failed to read frame after 3 attempts: {e}")
                time.sleep(0.01)  # Đợi 10ms rồi thử lại
    except Exception as e:
        print(f"❌ Error reading frame: {e}")
    
    return None

def gen_frames(camera_id):
    """
    🎬 GENERATOR MJPEG STREAM - Chạy liên tục cho mỗi client
    
    Mục đích: Tạo infinite stream của MJPEG frames cho browser
    
    Args:
        camera_id (str): ID camera
    
    Yields:
        bytes: MJPEG frame với multipart boundary
    
    Flow:
        Loop vô hạn:
          1. Đọc frame mới từ file (via get_stream_frame)
          2. Nếu có frame mới → yield frame mới
          3. Nếu không có frame mới → yield frame cũ (QUAN TRỌNG: giữ connection)
          4. Sleep 33ms (~30 FPS)
          5. Lặp lại
    
    Error Handling:
        - GeneratorExit: Client đóng tab/refresh → exit gracefully
        - Exception: Log error nhưng tiếp tục (không crash)
        - Max 50 errors liên tiếp → dừng để tránh infinite loop
    """
    import time
    last_frame = None  # Cache frame cuối cùng
    error_count = 0
    max_errors = 50
    
    print(f"🎬 Starting stream generator for: {camera_id}")
    
    while True:  # ♾️ Infinite loop (cho đến khi client disconnect)
        try:
            # 📖 Đọc frame mới từ file
            frame = get_stream_frame(camera_id)
            
            if frame is not None:
                # ✅ Có frame mới → update cache và yield
                last_frame = frame
                error_count = 0  # Reset error counter
                yield (b'--frame\r\nContent-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')
                
            elif last_frame is not None:
                # 🔁 Không có frame mới → yield frame cũ (QUAN TRỌNG!)
                # Lý do: Phải yield gì đó để giữ HTTP connection alive
                yield (b'--frame\r\nContent-Type: image/jpeg\r\n\r\n' + last_frame + b'\r\n')
                
            else:
                # ⏳ Chưa có frame nào (lần đầu khởi động)
                error_count += 1
                if error_count > max_errors:
                    print(f"❌ Too many errors ({error_count}), stopping stream for {camera_id}")
                    break
                time.sleep(0.1)
                continue  # Skip yield, chờ frame đầu tiên
            
            # ⏱️ Sleep để maintain ~30 FPS (1/30 = 0.033s)
            time.sleep(0.033)
            
        except GeneratorExit:
            # 🔌 Client đóng connection (đóng tab, refresh, etc.)
            print(f"🔌 Stream closed by client: {camera_id}")
            break
            
        except Exception as e:
            # ⚠️ Unexpected error → log nhưng tiếp tục
            error_count += 1
            print(f"⚠️ Error in gen_frames for {camera_id}: {e} (error #{error_count})")
            if error_count > max_errors:
                print(f"❌ Too many errors ({error_count}), stopping stream")
                break
            time.sleep(0.1)

@login_required
def video_feed(request, src):
    """
    🎥 API ENDPOINT - MJPEG Video Stream
    
    URL: /video_feed/<camera_id>
    Method: GET
    Authentication: Required (login_required)
    
    Mục đích: Cung cấp MJPEG stream cho browser
    
    Args:
        request: Django HTTP request
        src (str): Camera ID (vd: 'raspberrypi_cam')
    
    Returns:
        StreamingHttpResponse: MJPEG stream với multipart/x-mixed-replace
    
    Headers:
        Content-Type: multipart/x-mixed-replace; boundary=frame
        Cache-Control: no-cache (buộc browser không cache)
        Pragma: no-cache (HTTP/1.0 compatibility)
        Expires: 0 (expire ngay lập tức)
    
    How it works:
        1. Browser tạo GET request
        2. Django tạo StreamingHttpResponse với gen_frames generator
        3. Generator liên tục yield frames
        4. Browser hiển thị frames như video (MJPEG format)
    """
    print(f"🎥 Stream request: {src} from {request.user.username} ({request.META.get('REMOTE_ADDR', 'unknown')})")
    
    response = StreamingHttpResponse(
        gen_frames(src),  # Generator function (yields frames)
        content_type='multipart/x-mixed-replace; boundary=frame'  # MJPEG format
    )
    
    # 🔧 Anti-cache headers (buộc browser luôn fetch mới)
    response['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    response['Pragma'] = 'no-cache'
    response['Expires'] = '0'
    response['X-Accel-Buffering'] = 'no'  # Disable nginx buffering nếu có
    
    print(f"✅ Stream response created for: {src}")
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
    isSensor = False
    sensorAPI = "http://172.20.10.2:5000/sensors"
    sensor_port = 0
    
    # Fetch sensor data
    try:
        import requests
        response = requests.get(sensorAPI, timeout=2)
        if response.status_code == 200:
            sensor_data = response.json()
            filtered = sensor_data.get("filtered", {})
            # Nếu có ít nhất 1 sensor có giá trị filtered (không None)
            if filtered.get("sensor1") is not None or filtered.get("sensor2") is not None:
                isSensor = True
                print(f"🟢 Sensor detected: {filtered}")
                sensor_port = 1 if filtered.get("sensor1") is not None else 2
            else:
                print(f"⚪ No vehicle detected (all filtered values are None)")
        else:
            print(f"⚠️ Sensor API returned status {response.status_code}")
    except requests.exceptions.Timeout:
        print("⚠️ Sensor API timeout")
    except requests.exceptions.RequestException as e:
        print(f"⚠️ Sensor API error: {e}")
    except Exception as e:
        print(f"❌ Unexpected error fetching sensor: {e}")

    if request.method == "POST" and isSensor:
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

            # ⭐ TỰ ĐỘNG XÁC ĐỊNH EVENT TYPE (Lần 1 = ENTRY, Lần 2 = EXIT)
            active_session = ParkingSession.objects.filter(
                license_plate=plate,
                status='ACTIVE'
            ).first()

            if sensor_port == 1:
                event_type = 'ENTRY'
                message = f'🚗 Xe {plate} VÀO bãi'
            if sensor_port == 2:
                event_type = 'EXIT'
                message = f'🚗 Xe {plate} RA bãi'
         
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
                print(f"ENTRY: {plate} from {source} ({confidence:.2%}) -> Session #{session.id}")
                
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
    """
    📤 API ENDPOINT - Nhận frame từ Raspberry Pi
    
    URL: /api/stream/<camera_id>
    Method: POST
    Body: Binary JPEG data
    
    Mục đích: Nhận và lưu frame từ Raspberry Pi vào file
    
    Args:
        request: Django HTTP request với binary JPEG trong body
        src (str): Camera ID (vd: 'raspberrypi_cam')
    
    Returns:
        HttpResponse: "OK" hoặc error message
    
    Flow:
        1. Raspberry Pi POST binary JPEG → Django
        2. Django lưu vào media/streams/<camera_id>.jpg (ATOMIC WRITE)
        3. Return "OK"
        4. video_feed() sẽ đọc file này để stream cho browser
    
    Atomic Write:
        - Ghi vào file .tmp trước
        - Sau đó move sang file chính
        - Tránh race condition khi đọc file đang được ghi
    """
    if request.method == 'POST':
        try:
            import os
            import shutil
            
            # 📁 Tạo thư mục nếu chưa có
            os.makedirs('media/streams', exist_ok=True)
            
            frame_path = f'media/streams/{src}.jpg'
            temp_path = f'media/streams/{src}.tmp'
            
            # ✅ Step 1: Ghi vào file tạm trước (atomic write)
            with open(temp_path, 'wb') as f:
                f.write(request.body)
            
            # ✅ Step 2: Move atomic (tránh đọc file đang ghi)
            shutil.move(temp_path, frame_path)
            
            return HttpResponse("OK", status=200)
            
        except Exception as e:
            print(f"❌ Error saving stream frame: {e}")
            return HttpResponse(str(e), status=500)
    
    return HttpResponse("Only POST allowed", status=405)

from django.http import StreamingHttpResponse
from django.views.decorators import gzip

import os
import time


def parking_history(request):
    # render template lịch sử
    return render(request, 'parking/parking_history.html')
