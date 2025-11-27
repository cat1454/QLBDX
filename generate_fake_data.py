"""
Script để tạo fake data cho hệ thống Smart Parking
- Tạo VehicleDetection (phát hiện xe từ camera)
- Tạo ParkingSession (phiên đỗ xe với doanh thu)
"""

import os
import django
import random
from datetime import datetime, timedelta
from decimal import Decimal

# Setup Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'smartparking.settings')
django.setup()

from parking.models import VehicleDetection, ParkingSession
from django.utils import timezone

# Danh sách biển số xe giả lập
FAKE_PLATES = [
    '29A12345', '30B67890', '51C11111', '59D22222', '79E33333',
    '29F44444', '30G55555', '51H66666', '59K77777', '79L88888',
    '29M99999', '30N00000', '51P12121', '59Q23232', '79R34343',
    '29S45454', '30T56565', '51U67676', '59V78787', '79X89898',
    '29Y90909', '30Z01010', '51A11122', '59B22233', '79C33344',
    '29D44455', '30E55566', '51F66677', '59G77788', '79H88899',
]

# Camera sources
CAMERA_SOURCES = ['raspberrypi_cam', 'camera_entry', 'camera_exit']

def random_datetime(start_date, end_date):
    """Tạo datetime ngẫu nhiên trong khoảng thời gian"""
    delta = end_date - start_date
    random_seconds = random.randint(0, int(delta.total_seconds()))
    return start_date + timedelta(seconds=random_seconds)

def generate_parking_duration():
    """
    Sinh thời lượng đỗ xe ngẫu nhiên (phút)
    - 40% xe đỗ ngắn (5-60 phút): 5.000đ
    - 30% xe đỗ trung bình (60-120 phút): 5.000đ - 8.000đ  
    - 20% xe đỗ lâu (120-300 phút): 8.000đ - 16.000đ
    - 10% xe đỗ rất lâu (300-600 phút): 16.000đ+
    """
    rand = random.random()
    if rand < 0.4:
        return random.randint(5, 60)
    elif rand < 0.7:
        return random.randint(60, 120)
    elif rand < 0.9:
        return random.randint(120, 300)
    else:
        return random.randint(300, 600)

def generate_fake_data(num_sessions=50, days_back=30):
    """
    Tạo fake data cho hệ thống
    
    Args:
        num_sessions: Số lượng phiên đỗ xe cần tạo
        days_back: Số ngày quá khứ để tạo data
    """
    print(f"🚀 Bắt đầu tạo {num_sessions} phiên đỗ xe fake...")
    
    # Xóa data cũ (tùy chọn - comment dòng này nếu muốn giữ data cũ)
    print("🗑️  Xóa data cũ...")
    VehicleDetection.objects.all().delete()
    ParkingSession.objects.all().delete()
    
    # Khởi tạo thời gian
    end_date = timezone.now()
    start_date = end_date - timedelta(days=days_back)
    
    created_sessions = 0
    created_detections = 0
    total_revenue = Decimal(0)
    
    for i in range(num_sessions):
        # Chọn biển số ngẫu nhiên
        plate = random.choice(FAKE_PLATES)
        camera = random.choice(CAMERA_SOURCES)
        
        # Tạo thời điểm vào
        entry_time = random_datetime(start_date, end_date)
        
        # Tạo thời lượng đỗ xe
        duration_minutes = generate_parking_duration()
        exit_time = entry_time + timedelta(minutes=duration_minutes)
        
        # Đảm bảo exit_time không vượt quá hiện tại
        if exit_time > timezone.now():
            exit_time = timezone.now()
            duration_minutes = int((exit_time - entry_time).total_seconds() / 60)
        
        # Tạo confidence score ngẫu nhiên (0.75-0.99)
        entry_confidence = round(random.uniform(0.75, 0.99), 2)
        exit_confidence = round(random.uniform(0.75, 0.99), 2)
        
        # Tạo VehicleDetection cho ENTRY
        entry_detection = VehicleDetection.objects.create(
            license_plate=plate,
            confidence=entry_confidence,
            detected_at=entry_time,
            event_type='ENTRY',
            camera_source=camera,
            image_path=f'detections/{plate}_entry_{entry_time.strftime("%Y%m%d_%H%M%S")}.jpg'
        )
        created_detections += 1
        
        # Quyết định xem phiên đã hoàn thành hay chưa
        # 80% phiên đã hoàn thành (có EXIT), 20% đang đỗ (ACTIVE)
        is_completed = random.random() < 0.8
        
        if is_completed:
            # Tạo VehicleDetection cho EXIT
            exit_detection = VehicleDetection.objects.create(
                license_plate=plate,
                confidence=exit_confidence,
                detected_at=exit_time,
                event_type='EXIT',
                camera_source=camera,
                image_path=f'detections/{plate}_exit_{exit_time.strftime("%Y%m%d_%H%M%S")}.jpg'
            )
            created_detections += 1
            
            # Tạo ParkingSession hoàn chỉnh
            session = ParkingSession.objects.create(
                license_plate=plate,
                entry_time=entry_time,
                exit_time=exit_time,
                duration_minutes=duration_minutes,
                status='COMPLETED',
                entry_image=entry_detection.image_path,
                exit_image=exit_detection.image_path,
            )
            
            # Tính phí
            session.fee = session.calculate_fee(duration_minutes)
            
            # Trạng thái thanh toán (70% đã thanh toán, 30% chưa)
            if random.random() < 0.7:
                session.payment_status = 'PAID'
                total_revenue += session.fee
            else:
                session.payment_status = 'UNPAID'
            
            session.save()
            
        else:
            # Tạo phiên đang đỗ (ACTIVE) - chỉ có ENTRY
            session = ParkingSession.objects.create(
                license_plate=plate,
                entry_time=entry_time,
                status='ACTIVE',
                payment_status='UNPAID',
                entry_image=entry_detection.image_path,
            )
        
        created_sessions += 1
        
        # In progress mỗi 10 phiên
        if (i + 1) % 10 == 0:
            print(f"   ✓ Đã tạo {i + 1}/{num_sessions} phiên...")
    
    # Thống kê
    print("\n" + "="*60)
    print("📊 THỐNG KÊ FAKE DATA")
    print("="*60)
    print(f"✅ Tổng số phiên đỗ xe: {created_sessions}")
    print(f"✅ Tổng số detection events: {created_detections}")
    
    active_sessions = ParkingSession.objects.filter(status='ACTIVE').count()
    completed_sessions = ParkingSession.objects.filter(status='COMPLETED').count()
    paid_sessions = ParkingSession.objects.filter(payment_status='PAID').count()
    unpaid_sessions = ParkingSession.objects.filter(payment_status='UNPAID').count()
    
    print(f"\n📍 Phiên đang đỗ (ACTIVE): {active_sessions}")
    print(f"✓ Phiên đã hoàn thành (COMPLETED): {completed_sessions}")
    print(f"💰 Đã thanh toán (PAID): {paid_sessions}")
    print(f"⏳ Chưa thanh toán (UNPAID): {unpaid_sessions}")
    
    # Tính tổng doanh thu
    total_paid = ParkingSession.objects.filter(
        payment_status='PAID'
    ).aggregate(
        total=django.db.models.Sum('fee')
    )['total'] or Decimal(0)
    
    total_unpaid = ParkingSession.objects.filter(
        payment_status='UNPAID',
        status='COMPLETED'
    ).aggregate(
        total=django.db.models.Sum('fee')
    )['total'] or Decimal(0)
    
    print(f"\n💵 Tổng doanh thu đã thu: {total_paid:,.0f}đ")
    print(f"⏰ Tổng công nợ chưa thu: {total_unpaid:,.0f}đ")
    print(f"📈 Tổng doanh thu tiềm năng: {(total_paid + total_unpaid):,.0f}đ")
    
    # Phân tích theo khoảng thời gian
    print(f"\n⏱️  PHÂN TÍCH THỜI LƯỢNG ĐỖ XE")
    print("-" * 60)
    
    short_term = ParkingSession.objects.filter(
        duration_minutes__lte=60, status='COMPLETED'
    ).count()
    medium_term = ParkingSession.objects.filter(
        duration_minutes__gt=60, duration_minutes__lte=120, status='COMPLETED'
    ).count()
    long_term = ParkingSession.objects.filter(
        duration_minutes__gt=120, status='COMPLETED'
    ).count()
    
    print(f"🕐 Ngắn hạn (≤60p): {short_term} phiên")
    print(f"🕑 Trung bình (60-120p): {medium_term} phiên")
    print(f"🕒 Dài hạn (>120p): {long_term} phiên")
    
    # Phân tích doanh thu theo ngày
    print(f"\n📅 TOP 5 NGÀY DOANH THU CAO NHẤT")
    print("-" * 60)
    
    from django.db.models.functions import TruncDate
    from django.db.models import Sum, Count
    
    daily_revenue = ParkingSession.objects.filter(
        payment_status='PAID',
        status='COMPLETED'
    ).annotate(
        date=TruncDate('entry_time')
    ).values('date').annotate(
        revenue=Sum('fee'),
        sessions=Count('id')
    ).order_by('-revenue')[:5]
    
    for idx, day in enumerate(daily_revenue, 1):
        print(f"{idx}. {day['date'].strftime('%d/%m/%Y')}: "
              f"{day['revenue']:,.0f}đ ({day['sessions']} phiên)")
    
    print("\n" + "="*60)
    print("✅ HOÀN THÀNH! Fake data đã được tạo thành công.")
    print("="*60)

if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description='Tạo fake data cho Smart Parking')
    parser.add_argument('--sessions', type=int, default=50, 
                        help='Số lượng phiên đỗ xe (mặc định: 50)')
    parser.add_argument('--days', type=int, default=30,
                        help='Số ngày quá khứ (mặc định: 30)')
    
    args = parser.parse_args()
    
    generate_fake_data(num_sessions=args.sessions, days_back=args.days)
