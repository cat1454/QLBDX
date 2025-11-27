"""
Django management command để tạo fake data cho Smart Parking
Sử dụng: python manage.py generate_parking_data --sessions 100 --days 30
"""

from django.core.management.base import BaseCommand
from django.utils import timezone
from parking.models import VehicleDetection, ParkingSession
from decimal import Decimal
import random
from datetime import datetime, timedelta


class Command(BaseCommand):
    help = 'Tạo fake data cho hệ thống Smart Parking (VehicleDetection và ParkingSession)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--sessions',
            type=int,
            default=50,
            help='Số lượng phiên đỗ xe cần tạo (mặc định: 50)',
        )
        parser.add_argument(
            '--days',
            type=int,
            default=30,
            help='Số ngày quá khứ để tạo data (mặc định: 30)',
        )
        parser.add_argument(
            '--clear',
            action='store_true',
            help='Xóa tất cả data cũ trước khi tạo mới',
        )

    def handle(self, *args, **options):
        num_sessions = options['sessions']
        days_back = options['days']
        clear_old = options['clear']

        self.stdout.write(self.style.SUCCESS(f'🚀 Bắt đầu tạo {num_sessions} phiên đỗ xe fake...'))

        # Xóa data cũ nếu được yêu cầu
        if clear_old:
            self.stdout.write('🗑️  Xóa data cũ...')
            VehicleDetection.objects.all().delete()
            ParkingSession.objects.all().delete()

        # Danh sách biển số xe giả lập
        FAKE_PLATES = [
            '29A12345', '30B67890', '51C11111', '59D22222', '79E33333',
            '29F44444', '30G55555', '51H66666', '59K77777', '79L88888',
            '29M99999', '30N00000', '51P12121', '59Q23232', '79R34343',
            '29S45454', '30T56565', '51U67676', '59V78787', '79X89898',
            '29Y90909', '30Z01010', '51A11122', '59B22233', '79C33344',
            '29D44455', '30E55566', '51F66677', '59G77788', '79H88899',
        ]

        CAMERA_SOURCES = ['raspberrypi_cam', 'camera_entry', 'camera_exit']

        # Khởi tạo thời gian
        end_date = timezone.now()
        start_date = end_date - timedelta(days=days_back)

        created_sessions = 0
        created_detections = 0

        for i in range(num_sessions):
            # Chọn biển số ngẫu nhiên
            plate = random.choice(FAKE_PLATES)
            camera = random.choice(CAMERA_SOURCES)

            # Tạo thời điểm vào
            delta = end_date - start_date
            random_seconds = random.randint(0, int(delta.total_seconds()))
            entry_time = start_date + timedelta(seconds=random_seconds)

            # Tạo thời lượng đỗ xe ngẫu nhiên
            rand = random.random()
            if rand < 0.4:
                duration_minutes = random.randint(5, 60)
            elif rand < 0.7:
                duration_minutes = random.randint(60, 120)
            elif rand < 0.9:
                duration_minutes = random.randint(120, 300)
            else:
                duration_minutes = random.randint(300, 600)

            exit_time = entry_time + timedelta(minutes=duration_minutes)

            # Đảm bảo exit_time không vượt quá hiện tại
            if exit_time > timezone.now():
                exit_time = timezone.now()
                duration_minutes = int((exit_time - entry_time).total_seconds() / 60)

            # Tạo confidence score ngẫu nhiên
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

            # 80% phiên đã hoàn thành, 20% đang đỗ
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

                # Trạng thái thanh toán (70% đã thanh toán)
                if random.random() < 0.7:
                    session.payment_status = 'PAID'
                else:
                    session.payment_status = 'UNPAID'

                session.save()

            else:
                # Tạo phiên đang đỗ (ACTIVE)
                session = ParkingSession.objects.create(
                    license_plate=plate,
                    entry_time=entry_time,
                    status='ACTIVE',
                    payment_status='UNPAID',
                    entry_image=entry_detection.image_path,
                )

            created_sessions += 1

            # In progress
            if (i + 1) % 10 == 0:
                self.stdout.write(f'   ✓ Đã tạo {i + 1}/{num_sessions} phiên...')

        # Thống kê
        self.stdout.write(self.style.SUCCESS('\n' + '='*60))
        self.stdout.write(self.style.SUCCESS('📊 THỐNG KÊ FAKE DATA'))
        self.stdout.write(self.style.SUCCESS('='*60))
        self.stdout.write(f'✅ Tổng số phiên đỗ xe: {created_sessions}')
        self.stdout.write(f'✅ Tổng số detection events: {created_detections}')

        active_sessions = ParkingSession.objects.filter(status='ACTIVE').count()
        completed_sessions = ParkingSession.objects.filter(status='COMPLETED').count()
        paid_sessions = ParkingSession.objects.filter(payment_status='PAID').count()
        unpaid_sessions = ParkingSession.objects.filter(payment_status='UNPAID').count()

        self.stdout.write(f'\n📍 Phiên đang đỗ (ACTIVE): {active_sessions}')
        self.stdout.write(f'✓ Phiên đã hoàn thành (COMPLETED): {completed_sessions}')
        self.stdout.write(f'💰 Đã thanh toán (PAID): {paid_sessions}')
        self.stdout.write(f'⏳ Chưa thanh toán (UNPAID): {unpaid_sessions}')

        # Tính doanh thu
        from django.db.models import Sum
        
        total_paid = ParkingSession.objects.filter(
            payment_status='PAID'
        ).aggregate(total=Sum('fee'))['total'] or Decimal(0)

        total_unpaid = ParkingSession.objects.filter(
            payment_status='UNPAID',
            status='COMPLETED'
        ).aggregate(total=Sum('fee'))['total'] or Decimal(0)

        self.stdout.write(f'\n💵 Tổng doanh thu đã thu: {total_paid:,.0f}đ')
        self.stdout.write(f'⏰ Tổng công nợ chưa thu: {total_unpaid:,.0f}đ')
        self.stdout.write(f'📈 Tổng doanh thu tiềm năng: {(total_paid + total_unpaid):,.0f}đ')

        # Phân tích thời lượng
        short_term = ParkingSession.objects.filter(
            duration_minutes__lte=60, status='COMPLETED'
        ).count()
        medium_term = ParkingSession.objects.filter(
            duration_minutes__gt=60, duration_minutes__lte=120, status='COMPLETED'
        ).count()
        long_term = ParkingSession.objects.filter(
            duration_minutes__gt=120, status='COMPLETED'
        ).count()

        self.stdout.write(f'\n⏱️  PHÂN TÍCH THỜI LƯỢNG ĐỖ XE')
        self.stdout.write('-' * 60)
        self.stdout.write(f'🕐 Ngắn hạn (≤60p): {short_term} phiên')
        self.stdout.write(f'🕑 Trung bình (60-120p): {medium_term} phiên')
        self.stdout.write(f'🕒 Dài hạn (>120p): {long_term} phiên')

        self.stdout.write(self.style.SUCCESS('\n' + '='*60))
        self.stdout.write(self.style.SUCCESS('✅ HOÀN THÀNH! Fake data đã được tạo thành công.'))
        self.stdout.write(self.style.SUCCESS('='*60))
