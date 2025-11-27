# 🎯 TEST THANH TOÁN KHI XE RA (EXIT) - HƯỚNG DẪN ĐƠN GIẢN

## ✅ Bước 1: Chuẩn bị dữ liệu test

### Tạo fake data (nếu chưa có):
```bash
cd H:\SmartParking\smartparking
python manage.py generate_parking_data --sessions 20 --days 7
```

Kết quả sẽ có:
- Khoảng 16 phiên đã hoàn thành (COMPLETED)
- Khoảng 4 phiên đang đỗ (ACTIVE)
- Một số phiên chưa thanh toán (UNPAID)

## ✅ Bước 2: Khởi động server

```bash
cd H:\SmartParking\smartparking
python manage.py runserver 0.0.0.0:8000
```

## ✅ Bước 3: Test với Django Shell (CÁCH DỄ NHẤT)

### 3.1. Mở Django shell (terminal mới):
```bash
cd H:\SmartParking\smartparking
python manage.py shell
```

### 3.2. Xem xe đang đỗ:
```python
from parking.models import ParkingSession
from django.utils import timezone

# Lấy các xe đang đỗ
active_sessions = ParkingSession.objects.filter(status='ACTIVE')

for s in active_sessions:
    print(f"🎫 {s.license_plate} - Vào lúc: {s.entry_time.strftime('%H:%M:%S')} - ID: {s.id}")
```

### 3.3. Giả lập xe ra (EXIT):
```python
# Chọn 1 session đang active
session = ParkingSession.objects.filter(status='ACTIVE').first()

if session:
    plate = session.license_plate
    print(f"\n🚗 Giả lập xe RA: {plate}")
    
    # Complete session (tự động tính phí)
    session.complete_session(timezone.now())
    
    print(f"✅ Hoàn thành!")
    print(f"   Thời gian đỗ: {session.duration_minutes} phút")
    print(f"   Phí: {session.fee:,}đ")
    print(f"   Trạng thái TT: {session.payment_status}")
    
    # Tạo VehicleDetection cho EXIT
    from parking.models import VehicleDetection
    detection = VehicleDetection.objects.create(
        license_plate=plate,
        confidence=0.95,
        event_type='EXIT',
        camera_source='manual_test'
    )
    print(f"\n🎯 Detection EXIT đã tạo - ID: {detection.id}")
else:
    print("❌ Không có xe đang đỗ!")
    print("💡 Chạy lại: python manage.py generate_parking_data --sessions 20")
```

## ✅ Bước 4: Kiểm tra Payment Modal

### 4.1. Mở Dashboard:
```
http://192.168.1.184:8000/dashboard_user/
```

### 4.2. Login với tài khoản nhân viên:
- Username: `staff` (hoặc user bạn đã tạo)
- Password: mật khẩu tương ứng

### 4.3. Quan sát:
- Dashboard sẽ update mỗi 3 giây
- Khi phát hiện EXIT event mới, payment modal sẽ **TỰ ĐỘNG HIỆN**
- Modal hiển thị:
  - Biển số xe
  - Thời gian đỗ
  - Chi tiết phí
  - Nút thanh toán

### 4.4. Test thanh toán:
1. Click nút **"💳 THANH TOÁN NGAY"**
2. Hệ thống sẽ:
   - Gọi API `/api/sessions/<id>/pay/`
   - Đánh dấu session là PAID
   - Đóng modal
   - Hiển thị thông báo thành công

## 🎯 Test nhanh với Python (không cần shell)

### Tạo file `quick_test.py`:
```python
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'smartparking.settings')
django.setup()

from parking.models import ParkingSession, VehicleDetection
from django.utils import timezone

# 1. Lấy xe đang đỗ
print("\n🚗 XE ĐANG ĐỖ:")
active = ParkingSession.objects.filter(status='ACTIVE')
for i, s in enumerate(active[:5], 1):
    print(f"{i}. {s.license_plate} (ID: {s.id})")

# 2. Chọn xe đầu tiên để test EXIT
if active.exists():
    session = active.first()
    plate = session.license_plate
    
    print(f"\n🚪 Giả lập EXIT: {plate}")
    
    # Complete session
    session.complete_session(timezone.now())
    
    # Tạo detection
    VehicleDetection.objects.create(
        license_plate=plate,
        confidence=0.95,
        event_type='EXIT',
        camera_source='test'
    )
    
    print(f"✅ Thành công!")
    print(f"   Phí: {session.fee:,}đ")
    print(f"   Trạng thái: {session.payment_status}")
    print(f"\n🎯 Mở dashboard để xem payment modal!")
    print(f"   http://192.168.1.184:8000/dashboard_user/")
else:
    print("❌ Không có xe đang đỗ")
```

### Chạy:
```bash
cd H:\SmartParking\smartparking
python quick_test.py
```

## 🔍 Debug: Kiểm tra API

### Check unpaid sessions:
```bash
curl http://192.168.1.184:8000/api/sessions/unpaid/
```

### Check latest detection:
```bash
curl http://192.168.1.184:8000/api/latest_detections/
```

### Check active sessions:
```bash
curl http://192.168.1.184:8000/api/sessions/active/
```

## 📊 Flow hoạt động

```
1. Xe ra → Raspberry Pi gửi ảnh + biển số
                ↓
2. API /api/upload/ nhận request
                ↓
3. Tìm ParkingSession ACTIVE với biển số đó
                ↓
4. Gọi complete_session() → Tính phí
                ↓
5. Tạo VehicleDetection với event_type='EXIT'
                ↓
6. Dashboard polling /api/latest_detections/ mỗi 3s
                ↓
7. Phát hiện EXIT → Gọi /api/sessions/unpaid/
                ↓
8. Tìm thấy session → Hiển thị payment modal
                ↓
9. User click "THANH TOÁN" → Gọi /api/sessions/<id>/pay/
                ↓
10. Session.payment_status = 'PAID' → Modal đóng
```

## 🐛 Troubleshooting

### Modal không hiện?

1. **Mở Console (F12)** - xem log:
```javascript
// Nên thấy:
🚗 New EXIT detected: 29A12345
✅ Found unpaid session, showing payment modal
```

2. **Kiểm tra detection có event type không**:
```python
from parking.models import VehicleDetection
latest = VehicleDetection.objects.latest('detected_at')
print(f"Event: {latest.event_type}")  # Phải là 'EXIT'
```

3. **Kiểm tra unpaid sessions**:
```python
from parking.models import ParkingSession
unpaid = ParkingSession.objects.filter(
    status='COMPLETED',
    payment_status='UNPAID'
)
print(f"Unpaid: {unpaid.count()}")
for s in unpaid:
    print(f"- {s.license_plate}: {s.fee}đ")
```

### Sensor check blocking?

Nếu không có sensor và muốn bỏ qua check, sửa `views.py`:

```python
@csrf_exempt
def upload_license_plate(request):
    isSensor = True  # ← Sửa thành True để bypass sensor check
    # ... rest of code
```

## 🎬 Demo Video (tự test)

1. Mở 2 cửa sổ:
   - Cửa sổ 1: Django shell
   - Cửa sổ 2: Dashboard (browser)

2. Trong shell, chạy:
```python
from parking.models import ParkingSession, VehicleDetection
from django.utils import timezone

session = ParkingSession.objects.filter(status='ACTIVE').first()
session.complete_session(timezone.now())
VehicleDetection.objects.create(
    license_plate=session.license_plate,
    confidence=0.95,
    event_type='EXIT',
    camera_source='test'
)
```

3. Xem dashboard → Modal tự động hiện sau 3 giây!

## ✅ Checklist test thành công

- [ ] Django server đang chạy
- [ ] Đã tạo fake data (có session ACTIVE)
- [ ] Chạy complete_session() trong shell/script
- [ ] Tạo VehicleDetection với event_type='EXIT'
- [ ] Dashboard đã login
- [ ] Dashboard đang ở trang dashboard_user
- [ ] Đợi 3 giây để polling update
- [ ] Payment modal xuất hiện ✨
- [ ] Click thanh toán → API call thành công
- [ ] Modal đóng → Session status = PAID
