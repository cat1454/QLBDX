# 🧪 HƯỚNG DẪN TEST CHỨC NĂNG THANH TOÁN KHI XE RA (EXIT)

## 📋 Tổng quan

Khi xe ra bãi (EXIT event), hệ thống sẽ:
1. Nhận diện biển số xe từ Raspberry Pi
2. Tìm session ACTIVE tương ứng
3. Tính toán phí đỗ xe tự động
4. Hiển thị payment modal trên dashboard nhân viên
5. Cho phép thanh toán và mở barrier

## 🎯 Các cách test

### Cách 1: Test với fake data có sẵn

1. **Tạo fake data** (nếu chưa có):
```bash
cd smartparking
python manage.py generate_parking_data --sessions 50 --days 7
```

2. **Kiểm tra các session unpaid**:
```bash
python test_payment_on_exit.py --mode check
```

3. **Giả lập EXIT cho một xe trong fake data**:
```bash
python test_payment_on_exit.py --mode existing
```

4. **Mở dashboard và xem payment modal tự động hiện**:
   - Truy cập: http://192.168.1.184:8000/dashboard_user/
   - Login với tài khoản nhân viên
   - Modal sẽ tự động xuất hiện với thông tin xe vừa EXIT

### Cách 2: Test flow đầy đủ (ENTRY → EXIT)

```bash
python test_payment_on_exit.py --mode full
```

Script sẽ tự động:
1. Tạo event ENTRY (xe vào)
2. Đợi 3 giây
3. Tạo event EXIT (xe ra)
4. Kiểm tra unpaid sessions
5. Hiển thị payment modal trên dashboard

### Cách 3: Test EXIT cho biển số cụ thể

```bash
python test_payment_on_exit.py --mode exit --plate 29A12345
```

### Cách 4: Test thủ công với API

Sử dụng Postman hoặc curl:

```bash
# Kiểm tra unpaid sessions
curl http://192.168.1.184:8000/api/sessions/unpaid/

# Giả lập EXIT (cần có ảnh)
curl -X POST http://192.168.1.184:8000/api/upload/ \
  -F "plate=29A12345" \
  -F "confidence=0.95" \
  -F "source=test_camera" \
  -F "image=@test_plate.jpg"
```

## 🔍 Kiểm tra kết quả

### 1. Backend Console
Khi EXIT event được gửi, console sẽ hiển thị:
```
✅ EXIT: 29A12345 from test_camera (95.00%) -> 45p, 5,000 VNĐ
```

### 2. API Response
Response khi EXIT sẽ chứa:
```json
{
  "status": "ok",
  "event_type": "EXIT",
  "plate": "29A12345",
  "session_id": 123,
  "duration_minutes": 45,
  "fee": 5000,
  "payment_status": "UNPAID",
  "display_message": "Phí đỗ xe: 5,000đ (45 phút)",
  "fee_breakdown": {
    "duration_minutes": 45,
    "first_period_fee": 5000,
    "additional_hours": 0,
    "additional_fee": 0,
    "total": 5000
  }
}
```

### 3. Dashboard (Frontend)
- Payment modal tự động xuất hiện
- Hiển thị thông tin: biển số, thời gian đỗ, phí
- Nút "THANH TOÁN NGAY" để xác nhận
- Khi thanh toán thành công → barrier mở

### 4. Database
Kiểm tra trong Django admin hoặc shell:
```python
from parking.models import ParkingSession

# Xem session vừa hoàn thành
session = ParkingSession.objects.filter(
    license_plate='29A12345',
    status='COMPLETED'
).latest('exit_time')

print(f"Duration: {session.duration_minutes} minutes")
print(f"Fee: {session.fee}đ")
print(f"Payment: {session.payment_status}")
```

## 🐛 Troubleshooting

### Payment modal không hiện

1. **Kiểm tra console log** (F12 trong browser):
```javascript
// Nên thấy:
🚗 New EXIT detected: 29A12345
📋 Available unpaid sessions: ["29A12345", ...]
✅ Found unpaid session, showing payment modal
```

2. **Kiểm tra API unpaid sessions**:
```bash
curl http://192.168.1.184:8000/api/sessions/unpaid/
```

3. **Verify event type trong latest_detections**:
```bash
curl http://192.168.1.184:8000/api/latest_detections/
```

### EXIT không tạo session

1. **Kiểm tra có ENTRY trước đó không**:
```python
ParkingSession.objects.filter(
    license_plate='29A12345',
    status='ACTIVE'
).exists()
```

2. **Kiểm tra sensor API** (nếu dùng sensor):
   - Sensor phải detect để tạo EXIT
   - Kiểm tra: http://172.20.10.2:5000/sensors

### Phí tính sai

Công thức tính phí:
- ≤ 90 phút: 5.000đ
- > 90 phút: 5.000đ + (số giờ thêm × 3.000đ)

Ví dụ:
- 45 phút → 5.000đ
- 90 phút → 5.000đ
- 120 phút → 5.000đ + 3.000đ = 8.000đ
- 150 phút → 5.000đ + 3.000đ = 8.000đ (làm tròn lên)
- 180 phút → 5.000đ + 6.000đ = 11.000đ

## 📊 Test Scenarios

### Scenario 1: Đỗ ngắn hạn (< 90 phút)
```bash
# Entry: 14:00
# Exit: 14:30 (30 phút)
# Fee: 5.000đ
```

### Scenario 2: Đỗ vừa (90-180 phút)
```bash
# Entry: 14:00
# Exit: 16:30 (150 phút = 2.5 giờ)
# Fee: 5.000đ + 3.000đ = 8.000đ
```

### Scenario 3: Đỗ dài hạn (> 180 phút)
```bash
# Entry: 10:00
# Exit: 15:00 (300 phút = 5 giờ)
# Fee: 5.000đ + (3.5 giờ × 3.000đ) = 5.000đ + 12.000đ = 17.000đ
```

## 🔗 API Endpoints liên quan

- `POST /api/upload/` - Nhận detection từ Raspberry Pi
- `GET /api/latest_detections/` - Lấy detection mới nhất
- `GET /api/sessions/unpaid/` - Lấy danh sách session chưa thanh toán
- `POST /api/sessions/<id>/pay/` - Đánh dấu đã thanh toán
- `GET /api/sessions/active/` - Lấy session đang active
- `GET /api/sessions/history/` - Lịch sử giao dịch

## 📝 Notes

1. **Sensor requirement**: Code hiện tại yêu cầu sensor detect để tạo event. Nếu test không có sensor, cần tạm thời disable check này trong `upload_license_plate` view.

2. **Image requirement**: API yêu cầu upload ảnh. Script test tự động tạo ảnh giả nếu không có.

3. **Real-time updates**: Dashboard update mỗi 3 giây để check EXIT events mới.

4. **Modal auto-show**: Modal chỉ hiện 1 lần cho mỗi detection (dùng detection ID để track).

5. **Payment confirmation**: Sau khi thanh toán, modal tự động đóng và barrier mở.
