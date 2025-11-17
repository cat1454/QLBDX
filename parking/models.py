from django.db import models
from django.contrib.auth.models import User
from decimal import Decimal


# ========== MODELS CHO HỆ THỐNG PHÁT HIỆN XE TỰ ĐỘNG ==========

class VehicleDetection(models.Model):
    """
    Lưu trữ TẤT CẢ các lần phát hiện xe từ camera
    """
    EVENT_CHOICES = [
        ('ENTRY', 'Vào bãi'),
        ('EXIT', 'Ra bãi'),
    ]
    
    license_plate = models.CharField(max_length=20, db_index=True)
    confidence = models.FloatField()
    detected_at = models.DateTimeField(auto_now_add=True, db_index=True)
    event_type = models.CharField(max_length=10, choices=EVENT_CHOICES)
    image_path = models.ImageField(upload_to='detections/', null=True, blank=True)
    camera_source = models.CharField(max_length=50, default='raspberrypi_cam')
    
    class Meta:
        ordering = ['-detected_at']
        indexes = [
            models.Index(fields=['-detected_at', 'license_plate']),
        ]
    
    def __str__(self):
        return f"{self.license_plate} - {self.event_type} - {self.detected_at.strftime('%Y-%m-%d %H:%M:%S')}"


class ParkingSession(models.Model):
    """
    Quản lý giao dịch bãi đỗ xe: Từ lúc vào (ENTRY) đến lúc ra (EXIT)
    
    LOGIC TÍNH PHÍ:
    - 30 phút đầu: MIỄN PHÍ (0đ)
    - 1 giờ đầu tiên (sau 30p miễn phí): 5.000đ
    - Mỗi giờ tiếp theo: 3.000đ/giờ
    
    Ví dụ:
    - 20 phút: 0đ (miễn phí)
    - 45 phút: 5.000đ (vào giờ đầu)
    - 1h 30p: 5.000đ (giờ đầu) + 3.000đ (giờ thứ 2) = 8.000đ
    - 2h 45p: 5.000đ + 3.000đ + 3.000đ = 11.000đ
    """
    STATUS_CHOICES = [
        ('ACTIVE', 'Đang đỗ'),
        ('COMPLETED', 'Đã hoàn thành'),
    ]
    
    PAYMENT_STATUS_CHOICES = [
        ('UNPAID', 'Chưa thanh toán'),
        ('PAID', 'Đã thanh toán'),
        ('FREE', 'Miễn phí'),
    ]
    
    license_plate = models.CharField(max_length=20, db_index=True, verbose_name='Biển số xe')
    entry_time = models.DateTimeField(db_index=True, verbose_name='Thời điểm vào')
    exit_time = models.DateTimeField(null=True, blank=True, verbose_name='Thời điểm ra')
    duration_minutes = models.IntegerField(null=True, blank=True, verbose_name='Thời lượng đỗ (phút)')
    fee = models.DecimalField(max_digits=10, decimal_places=0, default=0, verbose_name='Số tiền phải trả')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='ACTIVE', verbose_name='Trạng thái')
    payment_status = models.CharField(max_length=20, choices=PAYMENT_STATUS_CHOICES, default='UNPAID', verbose_name='Trạng thái thanh toán')
    entry_image = models.CharField(max_length=255, null=True, blank=True, verbose_name='Ảnh lúc vào')
    exit_image = models.CharField(max_length=255, null=True, blank=True, verbose_name='Ảnh lúc ra')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Ngày tạo')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='Ngày cập nhật')
    
    class Meta:
        ordering = ['-entry_time']
        indexes = [
            models.Index(fields=['license_plate', 'status']),
            models.Index(fields=['-entry_time']),
            models.Index(fields=['payment_status']),
            models.Index(fields=['created_at']),
        ]
        verbose_name = 'Giao dịch đỗ xe'
        verbose_name_plural = 'Giao dịch đỗ xe'
    
    def calculate_fee(self, duration_minutes):
        """
        Tính phí dựa trên thời lượng đỗ xe (phút)
        
        CÔNG THỨC:
        - Vào bãi: 5.000đ (phí cố định cho 90 phút đầu)
        - duration > 90 phút: 5.000đ + (số_giờ_thêm * 3.000đ)
        
        Args:
            duration_minutes (int): Thời lượng đỗ xe tính bằng phút
            
        Returns:
            Decimal: Số tiền phải trả
        """
        import math
        
        # Ngay khi vào bãi đã tính 5.000đ
        # CASE 1: Đến 90 phút (1.5 giờ) - Phí cố định 5.000đ
        if duration_minutes <= 90:
            return Decimal(5000)
        
        # CASE 2: Hơn 90 phút
        # Trừ đi 90 phút đã tính
        remaining_minutes = duration_minutes - 90
        
        # Làm tròn LÊN số giờ (mỗi giờ 3.000đ)
        additional_hours = math.ceil(remaining_minutes / 60)
        additional_fee = additional_hours * 3000
        
        # Tổng phí = 5.000đ đầu + Giờ thêm
        total_fee = 5000 + additional_fee
        
        return Decimal(total_fee)
    
    def complete_session(self, exit_time, exit_image=None):
        """
        Kết thúc phiên đỗ xe và tính phí tự động
        
        WORKFLOW:
        1. Cập nhật thời điểm ra
        2. Tính thời lượng đỗ (phút)
        3. Tính phí dựa trên logic mới
        4. Xác định trạng thái thanh toán
        5. Đổi trạng thái thành COMPLETED
        
        Args:
            exit_time (datetime): Thời điểm xe ra
            exit_image (str, optional): Đường dẫn ảnh lúc ra
        """
        self.exit_time = exit_time
        self.exit_image = exit_image
        self.status = 'COMPLETED'
        
        # Tính thời gian đỗ (phút)
        duration = self.exit_time - self.entry_time
        self.duration_minutes = int(duration.total_seconds() / 60)
        
        # Tính phí theo công thức mới (luôn tính phí, không miễn phí)
        self.fee = self.calculate_fee(self.duration_minutes)
        
        # Luôn là UNPAID vì không còn miễn phí
        self.payment_status = 'UNPAID'
        
        self.save()
    
    def mark_as_paid(self):
        """Đánh dấu giao dịch đã thanh toán"""
        self.payment_status = 'PAID'
        self.save()
    
    def get_fee_breakdown(self):
        """
        Trả về chi tiết tính phí để hiển thị cho khách hàng
        
        Returns:
            dict: Chi tiết phí bao gồm giờ đầu, giờ thêm
        """
        import math
        
        if not self.duration_minutes:
            return {
                'first_period_fee': 0,
                'additional_hours': 0,
                'additional_fee': 0,
                'total': 0
            }
        
        breakdown = {
            'duration_minutes': self.duration_minutes,
            'first_period_fee': 5000,  # 90 phút đầu: 5.000đ
            'additional_hours': 0,
            'additional_fee': 0,
            'total': int(self.fee)
        }
        
        if self.duration_minutes > 90:
            remaining_minutes = self.duration_minutes - 90
            additional_hours = math.ceil(remaining_minutes / 60)
            breakdown['additional_hours'] = additional_hours
            breakdown['additional_fee'] = additional_hours * 3000
        
        return breakdown
    
    def __str__(self):
        if self.status == 'ACTIVE':
            return f"{self.license_plate} - Đang đỗ"
        else:
            return f"{self.license_plate} - {self.duration_minutes}p - {self.fee:,.0f}đ - {self.get_payment_status_display()}"
