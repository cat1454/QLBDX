"""
Quick test script - Giả lập EXIT và test payment modal
Chạy: python quick_exit_test.py
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'smartparking.settings')
django.setup()

from parking.models import ParkingSession, VehicleDetection
from django.utils import timezone

print("\n" + "="*70)
print("🧪 TEST PAYMENT MODAL - GIẢI LẬP XE RA (EXIT)")
print("="*70)

# 1. Kiểm tra xe đang đỗ
print("\n📋 Bước 1: Kiểm tra xe đang đỗ...")
active_sessions = ParkingSession.objects.filter(status='ACTIVE').order_by('-entry_time')

if not active_sessions.exists():
    print("❌ Không có xe nào đang đỗ!")
    print("\n💡 Tạo fake data trước:")
    print("   python manage.py generate_parking_data --sessions 20")
    exit(1)

print(f"✅ Tìm thấy {active_sessions.count()} xe đang đỗ:\n")
for i, session in enumerate(active_sessions[:10], 1):
    duration = (timezone.now() - session.entry_time).total_seconds() / 60
    print(f"   {i}. {session.license_plate}")
    print(f"      Vào lúc: {session.entry_time.strftime('%H:%M:%S')}")
    print(f"      Đã đỗ: {int(duration)} phút")
    print(f"      ID: {session.id}\n")

# 2. Chọn xe để test
print("="*70)
choice = input("👉 Chọn xe để test EXIT (1-10) hoặc Enter để chọn xe đầu: ").strip()

if choice and choice.isdigit():
    idx = int(choice) - 1
    if 0 <= idx < len(active_sessions):
        session = active_sessions[idx]
    else:
        print("❌ Số không hợp lệ, chọn xe đầu")
        session = active_sessions.first()
else:
    session = active_sessions.first()

plate = session.license_plate
session_id = session.id

print(f"\n{'='*70}")
print(f"🚗 ĐÃ CHỌN: {plate} (Session #{session_id})")
print("="*70)

# 3. Complete session (giả lập EXIT)
print("\n📋 Bước 2: Giả lập xe ra (EXIT)...")

duration_before = (timezone.now() - session.entry_time).total_seconds() / 60
print(f"   Thời gian đã đỗ: {int(duration_before)} phút")

# Complete session - tự động tính phí
session.complete_session(timezone.now())

print(f"\n✅ Session đã hoàn thành!")
print(f"   ⏱️  Thời lượng: {session.duration_minutes} phút")
print(f"   💰 Phí: {session.fee:,}đ")
print(f"   💳 Trạng thái: {session.payment_status}")

# Hiển thị chi tiết phí
breakdown = session.get_fee_breakdown()
print(f"\n📊 Chi tiết tính phí:")
print(f"   - 90 phút đầu: {breakdown['first_period_fee']:,}đ")
if breakdown['additional_hours'] > 0:
    print(f"   - Thêm {breakdown['additional_hours']} giờ: {breakdown['additional_fee']:,}đ")
print(f"   - TỔNG: {breakdown['total']:,}đ")

# 4. Tạo VehicleDetection EXIT
print(f"\n📋 Bước 3: Tạo detection EXIT...")

detection = VehicleDetection.objects.create(
    license_plate=plate,
    confidence=0.95,
    event_type='EXIT',
    camera_source='manual_test',
    detected_at=timezone.now()
)

print(f"✅ Detection EXIT đã tạo!")
print(f"   ID: {detection.id}")
print(f"   Event: {detection.event_type}")
print(f"   Time: {detection.detected_at.strftime('%H:%M:%S')}")

# 5. Hướng dẫn test tiếp
print("\n" + "="*70)
print("🎯 BƯỚC TIẾP THEO - KIỂM TRA PAYMENT MODAL")
print("="*70)

print(f"""
1. MỞ DASHBOARD trong browser:
   http://192.168.1.184:8000/dashboard_user/
   
2. LOGIN với tài khoản nhân viên

3. QUAN SÁT:
   - Dashboard sẽ tự động update mỗi 3 giây
   - Payment modal sẽ TỰ ĐỘNG HIỆN sau vài giây
   - Modal hiển thị thông tin xe {plate}
   
4. TEST THANH TOÁN:
   - Click nút "💳 THANH TOÁN NGAY"
   - Hệ thống sẽ gọi API thanh toán
   - Modal sẽ tự động đóng
   - Session status → PAID

5. XEM KẾT QUẢ:
   - Kiểm tra lại session trong database
   - Hoặc chạy: python manage.py shell
   
     from parking.models import ParkingSession
     s = ParkingSession.objects.get(id={session_id})
     print(f"Payment: {{s.payment_status}}")  # Nên là 'PAID'
""")

# 6. Thống kê tổng quan
print("="*70)
print("📊 THỐNG KÊ HIỆN TẠI")
print("="*70)

total_active = ParkingSession.objects.filter(status='ACTIVE').count()
total_unpaid = ParkingSession.objects.filter(
    status='COMPLETED',
    payment_status='UNPAID'
).count()
total_paid = ParkingSession.objects.filter(payment_status='PAID').count()

print(f"""
🚗 Xe đang đỗ (ACTIVE): {total_active}
💰 Chưa thanh toán (UNPAID): {total_unpaid}
✅ Đã thanh toán (PAID): {total_paid}
""")

print("="*70)
print("✅ TEST SETUP HOÀN TẤT!")
print("="*70)

print("\n💡 Tip: Để test thêm, chạy lại script này với xe khác")
print("🔄 Hoặc tạo thêm fake data: python manage.py generate_parking_data --sessions 10\n")
