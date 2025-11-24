# 🅿️ LOGIC KIỂM TRA BÃI ĐẦY VÀ TẠM DỪNG DETECTION

## 📊 Tổng quan

Hệ thống hiện đã có logic kiểm tra bãi đầy và **TỪ CHỐI xe vào** khi hết chỗ:

### 1. Cấu hình
- **Tổng số chỗ đỗ**: 4 slot (được định nghĩa trong `views.py` - `MAX_PARKING_SLOTS = 4`)
- **Nguồn dữ liệu chính xác**: `ParkingSession.objects.filter(status='ACTIVE').count()`
  - Đếm số phiên đang ACTIVE (xe đang đỗ)
  - KHÔNG dựa vào 8 detection gần nhất (vì có thể có nhiều detection duplicate)

---

## 🔄 Luồng xử lý khi Raspberry Pi POST detection

### Endpoint: `POST /api/upload/`

```python
# File: parking/views.py - Dòng 357-417

1. Raspberry Pi POST dữ liệu:
   - license_plate: "30A12345"
   - confidence: 0.95
   - image: file ảnh

2. Backend kiểm tra:
   ✅ Đếm số xe đang đỗ:
   current_parked = ParkingSession.objects.filter(status='ACTIVE').count()
   
   ✅ Kiểm tra xe này đã có session ACTIVE chưa:
   active_session = ParkingSession.objects.filter(
       license_plate=plate,
       status='ACTIVE'
   ).first()
   
   📌 XÁC ĐỊNH SỰ KIỆN:
   - Nếu active_session tồn tại → event_type = 'EXIT'
   - Nếu không → event_type = 'ENTRY'

3. KIỂM TRA BÃI ĐẦY (CHỈ KHI ENTRY):
   if event_type == 'ENTRY' and current_parked >= MAX_PARKING_SLOTS:
       # ⚠️ BÃI ĐẦY - TỪ CHỐI
       - Lưu VehicleDetection (để có log)
       - KHÔNG tạo ParkingSession
       - Trả về HTTP 503 Service Unavailable
       
4. Response khi bãi đầy:
   {
       "status": "parking_full",
       "msg": "Bãi đỗ xe đã đầy",
       "plate": "30A12345",
       "available_slots": 0,
       "total_slots": 4,
       "action": "deny_entry",
       "display_message": "BÃI ĐẦY! Vui lòng quay lại sau"
   }
   HTTP Status: 503
```

---

## 🤖 Cách Raspberry Pi xử lý response

### Code mẫu trên Raspberry Pi:

```python
import requests
import time

API_URL = "http://your-django-server.com/api/upload/"
DETECTION_ENABLED = True

def send_detection(license_plate, confidence, image_path):
    global DETECTION_ENABLED
    
    try:
        with open(image_path, 'rb') as img:
            files = {'image': img}
            data = {
                'plate': license_plate,
                'confidence': confidence,
                'source': 'raspberrypi_cam'
            }
            
            response = requests.post(API_URL, data=data, files=files, timeout=5)
            result = response.json()
            
            # ⚠️ KIỂM TRA STATUS CODE
            if response.status_code == 503:
                # Bãi đầy - Tạm dừng detection
                print(f"🔴 {result['display_message']}")
                DETECTION_ENABLED = False
                return False
            
            elif response.status_code == 200:
                # Thành công
                if result.get('available_slots', 4) > 0:
                    DETECTION_ENABLED = True  # Bật lại nếu có chỗ
                
                print(f"✅ {result['message']}")
                print(f"   Còn {result.get('available_slots', '?')} chỗ trống")
                
                if result['event_type'] == 'EXIT':
                    print(f"   Phí: {result.get('fee', 0):,}đ")
                
                return True
                
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

# Main loop
while True:
    if DETECTION_ENABLED:
        # Chạy AI detection
        license_plate, confidence, image_path = detect_license_plate()
        
        if confidence > 0.7:
            success = send_detection(license_plate, confidence, image_path)
            
            if not success:
                print("⏸️  Tạm dừng detection...")
                time.sleep(30)  # Đợi 30 giây trước khi thử lại
    else:
        # Polling để kiểm tra xem có chỗ trống chưa
        try:
            check_response = requests.get("http://your-django-server.com/api/parking/availability/")
            data = check_response.json()
            
            if data['available_slots'] > 0:
                print(f"✅ Có {data['available_slots']} chỗ trống - Bật lại detection")
                DETECTION_ENABLED = True
        except:
            pass
        
        time.sleep(5)  # Kiểm tra mỗi 5 giây
```

---

## 📡 API kiểm tra trạng thái bãi đỗ

### Endpoint: `GET /api/parking/availability/`

```http
GET /api/parking/availability/

Response:
{
    "success": true,
    "total_slots": 4,
    "occupied_slots": 4,
    "available_slots": 0,
    "is_full": true,
    "occupancy_rate": 1.0,
    "active_vehicles": [
        {
            "license_plate": "30A12345",
            "entry_time": "2025-11-20 08:30:00",
            "duration_minutes": 45,
            "session_id": 123
        },
        // ... 3 xe khác
    ]
}
```

**Sử dụng:**
- Raspberry Pi có thể poll endpoint này để biết khi nào có chỗ trống
- Dashboard web hiển thị real-time occupancy
- Tích hợp với mobile app hoặc display LED

---

## 🎯 Ưu điểm của phương pháp này

✅ **Chính xác**: Đếm từ database (ACTIVE sessions) thay vì phân tích 8 detection
✅ **Real-time**: Kiểm tra ngay khi xe vào
✅ **Tự động**: Không cần can thiệp thủ công
✅ **Tiết kiệm tài nguyên**: Tạm dừng AI detection khi đầy
✅ **Có log đầy đủ**: Vẫn lưu VehicleDetection ngay cả khi từ chối

---

## 🔧 Cấu hình tùy chỉnh

### Thay đổi số lượng chỗ đỗ:

```python
# File: parking/views.py - Dòng 379
MAX_PARKING_SLOTS = 6  # Thay đổi từ 4 → 6
```

### Thay đổi thời gian polling trên Raspberry Pi:

```python
# Trong vòng lặp chính
time.sleep(5)  # Kiểm tra mỗi 5 giây (có thể điều chỉnh)
```

---

## 📊 Monitoring & Debugging

### Kiểm tra số xe đang đỗ:
```bash
# Trong Django shell
python manage.py shell

>>> from parking.models import ParkingSession
>>> active = ParkingSession.objects.filter(status='ACTIVE')
>>> print(f"Đang có {active.count()} xe đỗ")
>>> for s in active:
...     print(f"- {s.license_plate} (vào lúc {s.entry_time})")
```

### Xem log từ Raspberry Pi:
```bash
# Server Django sẽ in:
✅ ENTRY: 30A12345 from raspberrypi_cam (95.00%) -> Session #123
🔴 BÃI ĐẦY: 4/4 - Từ chối xe 30A99999
✅ EXIT: 30A12345 from raspberrypi_cam (96.00%) -> 85p, 5,000 VNĐ
```

---

## ⚠️ Lưu ý quan trọng

1. **Database consistency**: Đảm bảo các session cũ đã được đánh dấu COMPLETED
2. **Network timeout**: Raspberry Pi nên có timeout khi POST (tránh treo)
3. **Image size**: Nén ảnh trước khi gửi để tiết kiệm bandwidth
4. **Security**: Trong production nên thêm API key authentication

---

## 🚀 Tính năng mở rộng

### 1. Thông báo đẩy (Push notification)
```python
# Khi có chỗ trống
if available_slots == 1:  # Còn 1 chỗ cuối
    send_push_notification("Bãi gần đầy - Chỉ còn 1 chỗ!")
```

### 2. Reservation system
```python
# Đặt chỗ trước
if event_type == 'ENTRY':
    if has_reservation(plate):
        # Ưu tiên xe đã đặt chỗ ngay cả khi đầy
        pass
```

### 3. Dynamic pricing
```python
# Tăng giá khi đông
if occupancy_rate > 0.8:
    apply_surge_pricing()
```

---

## 📞 Liên hệ

Nếu cần hỗ trợ tích hợp hoặc tùy chỉnh logic, vui lòng tham khảo:
- `DOCUMENTATION.md` - Tài liệu chi tiết hệ thống
- `parking/views.py` - File chứa logic chính
- `parking/models.py` - Database schema
