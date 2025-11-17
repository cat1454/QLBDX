# 📚 HỆ THỐNG QUẢN LÝ BÃI ĐỖ XE - TÀI LIỆU CHI TIẾT

## 🎯 TỔNG QUAN HỆ THỐNG

### Database Schema

#### 1. Bảng `ParkingSession` (Giao dịch đỗ xe)

| Field | Type | Mô tả |
|-------|------|-------|
| `id` | Integer | ID tự động tăng |
| `license_plate` | String(20) | Biển số xe (có index) |
| `entry_time` | DateTime | Thời điểm vào (có index) |
| `exit_time` | DateTime | Thời điểm ra |
| `duration_minutes` | Integer | Thời lượng đỗ (phút) |
| `fee` | Decimal | Số tiền phải trả |
| `status` | String | 'ACTIVE' hoặc 'COMPLETED' |
| `payment_status` | String | 'UNPAID', 'PAID', 'FREE' |
| `entry_image` | String | Đường dẫn ảnh lúc vào |
| `exit_image` | String | Đường dẫn ảnh lúc ra |
| `created_at` | DateTime | Thời gian tạo record |
| `updated_at` | DateTime | Thời gian cập nhật |

#### 2. Bảng `VehicleDetection` (Lịch sử phát hiện)

| Field | Type | Mô tả |
|-------|------|-------|
| `id` | Integer | ID tự động tăng |
| `license_plate` | String(20) | Biển số xe |
| `confidence` | Float | Độ chính xác AI |
| `detected_at` | DateTime | Thời điểm phát hiện |
| `event_type` | String | 'ENTRY' hoặc 'EXIT' |
| `image_path` | ImageField | Ảnh phát hiện |
| `camera_source` | String | Nguồn camera |

---

## 💰 LOGIC TÍNH PHÍ

### Công Thức Tính Phí

```
30 phút đầu: MIỄN PHÍ (0đ)
Từ 31-90 phút: 5.000đ (giờ đầu tiên)
Sau 90 phút: 5.000đ + (số_giờ_thêm × 3.000đ)
```

### Ví dụ Cụ Thể

| Thời gian đỗ | Tính toán | Phí |
|--------------|-----------|-----|
| 20 phút | Miễn phí | **0đ** |
| 45 phút | Giờ đầu | **5.000đ** |
| 1h 30p (90p) | Giờ đầu | **5.000đ** |
| 1h 45p (105p) | 5.000 + 1×3.000 | **8.000đ** |
| 2h 30p (150p) | 5.000 + 1×3.000 | **8.000đ** |
| 2h 45p (165p) | 5.000 + 2×3.000 | **11.000đ** |
| 4h 15p (255p) | 5.000 + 3×3.000 | **14.000đ** |

### Code Python Tính Phí

```python
def calculate_fee(duration_minutes):
    import math
    
    # CASE 1: 30 phút đầu - MIỄN PHÍ
    if duration_minutes <= 30:
        return 0
    
    # CASE 2: Từ 31 đến 90 phút - 5.000đ
    if duration_minutes <= 90:
        return 5000
    
    # CASE 3: Hơn 90 phút
    remaining_minutes = duration_minutes - 90
    additional_hours = math.ceil(remaining_minutes / 60)
    return 5000 + (additional_hours * 3000)
```

---

## 🔄 WORKFLOW HỆ THỐNG

### 1. Khi Xe VÀO Bãi

```
1. Camera Raspberry Pi phát hiện biển số
2. POST request đến /api/upload/
   - license_plate: "30A12345"
   - confidence: 0.95
   - image: file ảnh
   
3. Backend xử lý:
   - Kiểm tra xe có đang đỗ không (status=ACTIVE)
   - Nếu KHÔNG → Tạo ParkingSession mới với status=ACTIVE
   - Nếu CÓ → Bỏ qua (tránh duplicate)
   
4. Tạo VehicleDetection record với event_type=ENTRY
5. Response trả về:
   {
     "event_type": "ENTRY",
     "license_plate": "30A12345",
     "session_id": 123,
     "message": "Xe vào bãi thành công"
   }
```

### 2. Khi Xe RA Khỏi Bãi

```
1. Camera phát hiện biển số lần thứ 2
2. POST request đến /api/upload/ (giống ENTRY)

3. Backend xử lý:
   - Tìm ParkingSession đang ACTIVE của biển số này
   - Nếu TÌM THẤY:
     a. Gọi session.complete_session(exit_time, exit_image)
     b. Tính duration_minutes
     c. Tính fee theo công thức
     d. Set payment_status:
        - Nếu fee = 0 → payment_status = 'FREE'
        - Nếu fee > 0 → payment_status = 'UNPAID'
     e. Đổi status = 'COMPLETED'
   - Nếu KHÔNG TÌM THẤY → Xe chưa vào hoặc đã ra rồi
   
4. Tạo VehicleDetection record với event_type=EXIT
5. Response trả về:
   {
     "event_type": "EXIT",
     "license_plate": "30A12345",
     "session_id": 123,
     "duration_minutes": 85,
     "fee": 5000,
     "fee_breakdown": {
       "free_minutes": 30,
       "first_hour_fee": 5000,
       "additional_hours": 0,
       "total": 5000
     },
     "payment_status": "UNPAID"
   }
```

### 3. Thanh Toán

```
1. Nhân viên/Admin xem danh sách chưa thanh toán
   GET /api/sessions/unpaid/
   
2. Chọn giao dịch cần thanh toán
3. POST /api/sessions/{session_id}/pay/
4. Backend cập nhật payment_status = 'PAID'
5. In hóa đơn (nếu có)
```

---

## 📊 API ENDPOINTS

### API Thống Kê Doanh Thu

#### 1. Thống kê tổng quát
```http
GET /api/revenue/stats/?period=day&date=2025-11-17

Response:
{
  "success": true,
  "period": "day",
  "period_label": "17/11/2025",
  "total_revenue": 150000,
  "total_transactions": 25,
  "paid_transactions": 20,
  "unpaid_transactions": 3,
  "free_transactions": 2,
  "average_fee": 6000,
  "average_duration_minutes": 85
}
```

#### 2. Doanh thu theo ngày (biểu đồ)
```http
GET /api/revenue/daily/?days=7

Response:
{
  "success": true,
  "labels": ["17/11", "18/11", "19/11", ...],
  "revenue": [50000, 75000, 60000, ...],
  "transactions": [10, 15, 12, ...]
}
```

#### 3. Doanh thu theo tháng
```http
GET /api/revenue/monthly/?year=2025

Response:
{
  "success": true,
  "year": 2025,
  "labels": ["01/2025", "02/2025", ...],
  "revenue": [500000, 750000, ...],
  "transactions": [100, 150, ...]
}
```

### API Quản Lý Giao Dịch

#### 4. Danh sách xe đang đỗ
```http
GET /api/sessions/active/

Response:
{
  "success": true,
  "count": 5,
  "sessions": [
    {
      "id": 1,
      "license_plate": "30A12345",
      "entry_time": "2025-11-17 08:30:00",
      "duration_minutes": 45,
      "estimated_fee": 5000,
      "entry_image": "detections/entry_123.jpg"
    }
  ]
}
```

#### 5. Chi tiết giao dịch
```http
GET /api/sessions/123/

Response:
{
  "success": true,
  "session": {
    "id": 123,
    "license_plate": "30A12345",
    "entry_time": "2025-11-17 08:30:00",
    "exit_time": "2025-11-17 10:15:00",
    "duration_minutes": 105,
    "fee": 8000,
    "fee_breakdown": {
      "duration_minutes": 105,
      "free_minutes": 30,
      "first_hour_fee": 5000,
      "additional_hours": 1,
      "additional_fee": 3000,
      "total": 8000
    },
    "payment_status": "UNPAID",
    "status": "COMPLETED"
  }
}
```

#### 6. Đánh dấu đã thanh toán
```http
POST /api/sessions/123/pay/

Response:
{
  "success": true,
  "message": "Đã thanh toán thành công",
  "session": {
    "id": 123,
    "license_plate": "30A12345",
    "fee": 8000,
    "payment_status": "PAID"
  }
}
```

#### 7. Danh sách chưa thanh toán
```http
GET /api/sessions/unpaid/

Response:
{
  "success": true,
  "count": 3,
  "total_debt": 25000,
  "sessions": [...]
}
```

#### 8. Lịch sử giao dịch (có phân trang, filter)
```http
GET /api/sessions/history/?page=1&limit=20&license_plate=30A&payment_status=PAID&from_date=2025-11-01&to_date=2025-11-17

Response:
{
  "success": true,
  "page": 1,
  "limit": 20,
  "total": 150,
  "total_pages": 8,
  "sessions": [...]
}
```

---

## ⚠️ XỬ LÝ EDGE CASES

### 1. Xe vào 2 lần liên tiếp (không ra)
```
- Khi phát hiện ENTRY lần 2
- Kiểm tra: Đã có session ACTIVE chưa?
- Nếu CÓ → BỎ QUA (không tạo session mới)
- Log: "Xe đã vào rồi, bỏ qua detection này"
```

### 2. Xe ra nhưng chưa có lịch sử vào
```
- Khi phát hiện EXIT
- Kiểm tra: Có session ACTIVE không?
- Nếu KHÔNG → BỎ QUA
- Log: "Không tìm thấy session ENTRY, bỏ qua"
```

### 3. Xe đỗ qua đêm (hơn 24h)
```
- Logic tính phí vẫn hoạt động bình thường
- Ví dụ: 25 giờ = 1500 phút
  → 5.000 + ceil((1500-90)/60) × 3.000
  → 5.000 + 24 × 3.000 = 77.000đ
```

### 4. Camera nhận diện sai biển số
```
- Chỉ chấp nhận confidence > 0.7
- Admin có thể sửa biển số thủ công trong database
- Lưu ảnh để đối chiếu sau
```

### 5. Thanh toán trùng lặp
```python
if session.payment_status == 'PAID':
    return {"error": "Giao dịch đã được thanh toán rồi"}
```

### 6. Miễn phí (dưới 30 phút)
```
- payment_status tự động = 'FREE'
- Không cần thanh toán
- Vẫn lưu vào database để thống kê
```

---

## 🚀 TÍCH HỢP VỚI HỆ THỐNG NHẬN DIỆN

### Code Raspberry Pi (Python)

```python
import requests
import cv2

# Cấu hình
API_URL = "http://your-django-server.com/api/upload/"
CAMERA_ID = "raspberrypi_cam"

def detect_license_plate():
    # Code AI nhận diện biển số của bạn
    license_plate = "30A12345"
    confidence = 0.95
    image_path = "detected_image.jpg"
    return license_plate, confidence, image_path

def send_to_server(license_plate, confidence, image_path):
    with open(image_path, 'rb') as img:
        files = {'image': img}
        data = {
            'license_plate': license_plate,
            'confidence': confidence,
            'camera_source': CAMERA_ID
        }
        
        response = requests.post(API_URL, data=data, files=files)
        result = response.json()
        
        print(f"Event: {result['event_type']}")
        print(f"Message: {result['message']}")
        
        if result['event_type'] == 'EXIT':
            print(f"Phí: {result['fee']:,}đ")
            print(f"Thời gian: {result['duration_minutes']} phút")
            
            # Hiển thị lên màn hình LCD hoặc speaker
            display_on_screen(result)

# Main loop
while True:
    license_plate, confidence, image_path = detect_license_plate()
    
    if confidence > 0.7:  # Ngưỡng tin cậy
        send_to_server(license_plate, confidence, image_path)
    
    time.sleep(1)
```

---

## 📈 HƯỚNG NÂNG CẤP SAU NÀY

### 1. Vé Tháng (Monthly Pass)

#### Thêm bảng `MonthlyPass`
```python
class MonthlyPass(models.Model):
    license_plate = models.CharField(max_length=20, unique=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    start_date = models.DateField()
    end_date = models.DateField()
    fee = models.DecimalField(max_digits=10, decimal_places=0)
    status = models.CharField(choices=[('ACTIVE', 'Đang hoạt động'), ('EXPIRED', 'Hết hạn')])
```

#### Logic xử lý
```python
def complete_session(self, exit_time, exit_image=None):
    # Kiểm tra vé tháng
    monthly_pass = MonthlyPass.objects.filter(
        license_plate=self.license_plate,
        status='ACTIVE',
        start_date__lte=exit_time.date(),
        end_date__gte=exit_time.date()
    ).first()
    
    if monthly_pass:
        self.fee = 0
        self.payment_status = 'FREE'
        self.note = f"Vé tháng: {monthly_pass.id}"
    else:
        # Tính phí bình thường
        self.fee = self.calculate_fee(self.duration_minutes)
```

### 2. Ví Điện Tử (E-Wallet)

#### Thêm bảng `Wallet`
```python
class Wallet(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    balance = models.DecimalField(max_digits=10, decimal_places=0, default=0)
    
    def deduct(self, amount):
        if self.balance >= amount:
            self.balance -= amount
            self.save()
            return True
        return False

class WalletTransaction(models.Model):
    wallet = models.ForeignKey(Wallet, on_delete=models.CASCADE)
    amount = models.DecimalField(max_digits=10, decimal_places=0)
    type = models.CharField(choices=[('DEPOSIT', 'Nạp'), ('PAYMENT', 'Thanh toán')])
    parking_session = models.ForeignKey(ParkingSession, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
```

#### Logic tự động thanh toán
```python
def complete_session(self, exit_time, exit_image=None):
    # ... tính phí ...
    
    # Tự động trừ ví nếu có
    try:
        wallet = self.user.wallet
        if wallet.deduct(self.fee):
            self.payment_status = 'PAID'
            WalletTransaction.objects.create(
                wallet=wallet,
                amount=self.fee,
                type='PAYMENT',
                parking_session=self
            )
    except:
        self.payment_status = 'UNPAID'
```

### 3. Vai Trò Nhân Viên

#### Thêm permissions
```python
from django.contrib.auth.models import Permission

# Permissions
- parking.view_parkingsession
- parking.add_parkingsession
- parking.change_parkingsession
- parking.delete_parkingsession
- parking.can_mark_paid

# Decorator
from django.contrib.auth.decorators import permission_required

@permission_required('parking.can_mark_paid')
def mark_session_paid(request, session_id):
    # ...
```

#### Roles
- **Admin**: Toàn quyền
- **Cashier**: Chỉ xem và thanh toán
- **Viewer**: Chỉ xem thống kê

### 4. In Hóa Đơn (Receipt)

#### Cài thư viện
```bash
pip install reportlab
```

#### Code in PDF
```python
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

def generate_receipt(session):
    filename = f"receipt_{session.id}.pdf"
    c = canvas.Canvas(filename, pagesize=A4)
    
    # Header
    c.setFont("Helvetica-Bold", 16)
    c.drawString(100, 800, "HÓA ĐƠN THANH TOÁN")
    c.drawString(100, 780, "BÃI ĐỖ XE THÔNG MINH")
    
    # Thông tin
    c.setFont("Helvetica", 12)
    c.drawString(100, 750, f"Biển số xe: {session.license_plate}")
    c.drawString(100, 730, f"Thời gian vào: {session.entry_time}")
    c.drawString(100, 710, f"Thời gian ra: {session.exit_time}")
    c.drawString(100, 690, f"Thời lượng: {session.duration_minutes} phút")
    
    # Chi tiết phí
    breakdown = session.get_fee_breakdown()
    c.drawString(100, 660, "Chi tiết phí:")
    c.drawString(120, 640, f"- 30 phút miễn phí: 0đ")
    c.drawString(120, 620, f"- Giờ đầu: {breakdown['first_hour_fee']:,}đ")
    if breakdown['additional_hours'] > 0:
        c.drawString(120, 600, f"- {breakdown['additional_hours']} giờ thêm: {breakdown['additional_fee']:,}đ")
    
    # Tổng
    c.setFont("Helvetica-Bold", 14)
    c.drawString(100, 560, f"TỔNG CỘNG: {session.fee:,}đ")
    
    c.save()
    return filename
```

### 5. Thông Báo Realtime (WebSocket)

```python
# channels/consumers.py
from channels.generic.websocket import AsyncJsonWebsocketConsumer

class ParkingConsumer(AsyncJsonWebsocketConsumer):
    async def connect(self):
        await self.channel_layer.group_add("parking_updates", self.channel_name)
        await self.accept()
    
    async def parking_event(self, event):
        # Gửi thông báo realtime cho dashboard
        await self.send_json({
            'type': event['type'],
            'data': event['data']
        })

# Khi có xe vào/ra
from channels.layers import get_channel_layer
channel_layer = get_channel_layer()

async_to_sync(channel_layer.group_send)(
    "parking_updates",
    {
        "type": "parking_event",
        "data": {
            "event": "ENTRY",
            "license_plate": "30A12345"
        }
    }
)
```

---

## 📝 TESTING

### Test Tính Phí
```python
from parking.models import ParkingSession
from datetime import timedelta

# Test case 1: 20 phút - Miễn phí
session = ParkingSession()
assert session.calculate_fee(20) == 0

# Test case 2: 45 phút - Giờ đầu
assert session.calculate_fee(45) == 5000

# Test case 3: 1h 45p - Có giờ thêm
assert session.calculate_fee(105) == 8000

# Test case 4: 4h 15p
assert session.calculate_fee(255) == 14000
```

### Test API
```bash
# Test thống kê
curl http://localhost:8000/api/revenue/stats/?period=day

# Test thanh toán
curl -X POST http://localhost:8000/api/sessions/123/pay/

# Test lịch sử
curl "http://localhost:8000/api/sessions/history/?page=1&limit=10"
```

---

## 🎓 KẾT LUẬN

Hệ thống này cung cấp:
- ✅ Database đầy đủ với indexes
- ✅ Logic tính phí linh hoạt, dễ thay đổi
- ✅ API RESTful đầy đủ cho mọi chức năng
- ✅ Xử lý edge cases chặt chẽ
- ✅ Dễ tích hợp với AI nhận diện biển số
- ✅ Dễ nâng cấp thêm tính năng mới

**Ưu điểm:**
- Code dễ hiểu, có comment chi tiết
- Tách biệt logic tính phí (dễ test)
- API có validation đầy đủ
- Hỗ trợ timezone (UTC+7 Vietnam)
- Có pagination, filter cho lịch sử

**Sẵn sàng cho production!** 🚀
