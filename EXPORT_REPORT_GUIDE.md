# 📥 HƯỚNG DẪN SỬ DỤNG CHỨC NĂNG XUẤT BÁO CÁO CSV

## 🎯 Tổng quan

Hệ thống hỗ trợ xuất 2 loại báo cáo:
1. **💰 Báo cáo doanh thu** - Chi tiết giao dịch đỗ xe và thu chi
2. **🎥 Báo cáo phát hiện xe** - Lịch sử nhận diện biển số từ camera

## 📊 Cách sử dụng trên Dashboard Admin

### Bước 1: Truy cập Dashboard
```
http://192.168.1.184:8000/dashboard_admin/
```

### Bước 2: Click nút "📥 Xuất báo cáo"
- Nút nằm ở phần "🎯 Hành động nhanh" bên phải màn hình
- Màu xanh lá cây

### Bước 3: Chọn tùy chọn xuất báo cáo

#### A. Báo cáo doanh thu (mặc định)

**Khoảng thời gian:**
- 📅 **Hôm nay** - Giao dịch trong ngày hôm nay
- 📆 **Tuần này** - Giao dịch trong tuần (Thứ 2 - Chủ nhật)
- 📊 **Tháng này** - Giao dịch trong tháng hiện tại
- 📈 **Năm này** - Giao dịch trong năm hiện tại
- 📋 **Tùy chỉnh** - Chọn ngày bắt đầu và kết thúc tùy ý
- 🌍 **Tất cả** - Xuất toàn bộ dữ liệu

**Trạng thái thanh toán:**
- **Tất cả** - Bao gồm tất cả trạng thái
- ✅ **Đã thanh toán** - Chỉ giao dịch đã thanh toán
- ⏳ **Chưa thanh toán** - Chỉ giao dịch chưa thanh toán

#### B. Báo cáo phát hiện xe

**Số ngày quá khứ:**
- 1 ngày
- 7 ngày (mặc định)
- 30 ngày
- 90 ngày

**Loại sự kiện:**
- **Tất cả** - Cả vào và ra
- 🚗 **Vào bãi** - Chỉ xe vào
- 🚪 **Ra bãi** - Chỉ xe ra

### Bước 4: Click "📥 Tải xuống"
- File CSV sẽ tự động được tải về máy
- Tên file tự động theo định dạng: `bao_cao_doanh_thu_YYYY-MM.csv`

## 📄 Cấu trúc file CSV

### 1. Báo cáo doanh thu

```csv
STT,Biển số xe,Thời gian vào,Thời gian ra,Thời lượng (phút),Phí đỗ xe (VNĐ),Trạng thái thanh toán,Ngày tạo
1,29A12345,27/11/2025 10:30:00,27/11/2025 12:15:00,105,8000,Đã thanh toán,27/11/2025 12:15:05
2,30B67890,27/11/2025 09:00:00,27/11/2025 09:45:00,45,5000,Chưa thanh toán,27/11/2025 09:45:12
...

=== TỔNG KẾT ===
Tổng số giao dịch:,50
Tổng doanh thu:,"350,000 VNĐ"
Đã thu:,"280,000 VNĐ"
Chưa thu:,"70,000 VNĐ"
Ngày xuất báo cáo:,27/11/2025 14:30:00
```

### 2. Báo cáo phát hiện xe

```csv
STT,Biển số xe,Loại sự kiện,Độ tin cậy (%),Thời gian phát hiện,Camera nguồn,Đường dẫn ảnh
1,29A12345,Vào bãi,95.5,27/11/2025 10:30:15,raspberrypi_cam,detections/29A12345_entry_20251127_103015.jpg
2,29A12345,Ra bãi,93.2,27/11/2025 12:15:20,raspberrypi_cam,detections/29A12345_exit_20251127_121520.jpg
...

=== TỔNG KẾT ===
Tổng số phát hiện:,180
Số lần vào:,90
Số lần ra:,90
Ngày xuất:,27/11/2025 14:30:00
```

## 🔧 Sử dụng API trực tiếp

### Xuất báo cáo doanh thu:

**Endpoint:**
```
GET /api/export/revenue/
```

**Parameters:**
- `period`: 'day', 'week', 'month', 'year', 'all'
- `status`: 'all', 'paid', 'unpaid'
- `start_date`: 'YYYY-MM-DD' (dùng với period='custom')
- `end_date`: 'YYYY-MM-DD' (dùng với period='custom')

**Ví dụ:**
```bash
# Xuất doanh thu tháng này
curl -O http://192.168.1.184:8000/api/export/revenue/?period=month&status=all

# Xuất chỉ giao dịch đã thanh toán
curl -O http://192.168.1.184:8000/api/export/revenue/?period=month&status=paid

# Xuất theo khoảng tùy chỉnh
curl -O "http://192.168.1.184:8000/api/export/revenue/?start_date=2025-11-01&end_date=2025-11-30&status=all"
```

### Xuất báo cáo phát hiện:

**Endpoint:**
```
GET /api/export/detections/
```

**Parameters:**
- `days`: Số ngày quá khứ (1, 7, 30, 90)
- `event_type`: 'all', 'ENTRY', 'EXIT'

**Ví dụ:**
```bash
# Xuất 7 ngày gần nhất
curl -O http://192.168.1.184:8000/api/export/detections/?days=7&event_type=all

# Xuất chỉ xe vào trong 30 ngày
curl -O http://192.168.1.184:8000/api/export/detections/?days=30&event_type=ENTRY
```

## 📊 Sử dụng trong Python

```python
import requests
import pandas as pd
from io import StringIO

SERVER = "http://192.168.1.184:8000"

# Download và load vào pandas DataFrame
response = requests.get(f"{SERVER}/api/export/revenue/?period=month&status=all")

if response.status_code == 200:
    # Read CSV into DataFrame
    df = pd.read_csv(StringIO(response.text))
    
    # Phân tích dữ liệu
    print(f"Tổng giao dịch: {len(df)}")
    print(f"Tổng doanh thu: {df['Phí đỗ xe (VNĐ)'].sum():,}đ")
    
    # Vẽ biểu đồ
    df['Ngày'] = pd.to_datetime(df['Thời gian vào']).dt.date
    daily_revenue = df.groupby('Ngày')['Phí đỗ xe (VNĐ)'].sum()
    daily_revenue.plot(kind='bar', title='Doanh thu theo ngày')
```

## 🎨 Mở trong Excel/Google Sheets

### Excel:
1. Mở file CSV vừa tải
2. Excel tự động nhận diện encoding UTF-8
3. Dữ liệu hiển thị đúng tiếng Việt và định dạng số

### Google Sheets:
1. File → Import → Upload
2. Chọn file CSV
3. Import → Replace spreadsheet
4. Dữ liệu tự động format

## 🔐 Bảo mật

- ✅ API yêu cầu authentication (login)
- ✅ Chỉ admin mới có quyền xuất báo cáo
- ✅ File CSV có BOM header cho Excel UTF-8
- ✅ Dữ liệu được format chuẩn tiếng Việt

## 🐛 Xử lý lỗi

### Lỗi: "Không có dữ liệu"
- **Nguyên nhân**: Không có giao dịch trong khoảng thời gian đã chọn
- **Giải pháp**: Chọn khoảng thời gian khác hoặc tạo fake data

### Lỗi: "Định dạng ngày không hợp lệ"
- **Nguyên nhân**: Ngày bắt đầu/kết thúc không đúng format
- **Giải pháp**: Sử dụng format YYYY-MM-DD (ví dụ: 2025-11-27)

### Lỗi: "Không thể tải file"
- **Nguyên nhân**: Server chưa chạy hoặc không có quyền
- **Giải pháp**: Kiểm tra server và đăng nhập lại

## 📈 Use Cases

### 1. Báo cáo cuối ngày
```
Khoảng thời gian: Hôm nay
Trạng thái: Tất cả
→ Xem tổng quan hoạt động trong ngày
```

### 2. Đối soát công nợ
```
Khoảng thời gian: Tháng này
Trạng thái: Chưa thanh toán
→ Danh sách xe cần thu phí
```

### 3. Báo cáo kế toán tháng
```
Khoảng thời gian: Tháng trước (dùng Tùy chỉnh)
Trạng thái: Đã thanh toán
→ Doanh thu thực tế đã thu
```

### 4. Phân tích lưu lượng xe
```
Loại: Báo cáo phát hiện
Số ngày: 30 ngày
→ Thống kê xu hướng ra vào
```

## 🎯 Tips

1. **Xuất định kỳ**: Nên xuất báo cáo cuối mỗi ngày để backup dữ liệu
2. **Lưu trữ**: Tạo thư mục riêng cho các file CSV theo tháng
3. **Phân tích**: Import vào Excel/Google Sheets để tạo pivot table
4. **Tự động hóa**: Sử dụng API để tự động xuất và gửi email
5. **So sánh**: Xuất cùng kỳ năm trước để so sánh xu hướng

## 🔗 Tích hợp

### Gửi email tự động:
```python
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase

# Download CSV
response = requests.get(f"{SERVER}/api/export/revenue/?period=day")

# Send email with attachment
# ... (code gửi email)
```

### Lưu vào Google Drive:
```python
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

# Download CSV
# Upload to Google Drive
# ... (code upload)
```

## ✅ Checklist

- [ ] Django server đang chạy
- [ ] Đã có dữ liệu trong database
- [ ] Đã login với tài khoản admin
- [ ] Chọn đúng khoảng thời gian
- [ ] Chọn đúng loại báo cáo
- [ ] File CSV được tải về thành công
- [ ] Mở file và kiểm tra dữ liệu
- [ ] Lưu file vào thư mục backup
