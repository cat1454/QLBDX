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
    Quản lý phiên đỗ xe: Từ lúc vào (ENTRY) đến lúc ra (EXIT)
    """
    STATUS_CHOICES = [
        ('ACTIVE', 'Đang đỗ'),
        ('COMPLETED', 'Đã hoàn thành'),
    ]
    
    license_plate = models.CharField(max_length=20, db_index=True)
    entry_time = models.DateTimeField(db_index=True)
    exit_time = models.DateTimeField(null=True, blank=True)
    duration_minutes = models.IntegerField(null=True, blank=True)
    fee = models.DecimalField(max_digits=10, decimal_places=0, null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='ACTIVE')
    entry_image = models.CharField(max_length=255, null=True, blank=True)
    exit_image = models.CharField(max_length=255, null=True, blank=True)
    
    class Meta:
        ordering = ['-entry_time']
        indexes = [
            models.Index(fields=['license_plate', 'status']),
            models.Index(fields=['-entry_time']),
        ]
    
    def complete_session(self, exit_time, exit_image=None):
        """
        Kết thúc phiên đỗ xe và tính phí
        Phí: 20,000 VNĐ/giờ (làm tròn lên)
        """
        from django.utils import timezone
        import math
        
        self.exit_time = exit_time
        self.exit_image = exit_image
        self.status = 'COMPLETED'
        
        # Tính thời gian đỗ (phút)
        duration = self.exit_time - self.entry_time
        self.duration_minutes = int(duration.total_seconds() / 60)
        
        # Tính phí: 20,000 VNĐ/giờ, làm tròn lên
        hours = math.ceil(duration.total_seconds() / 3600)
        self.fee = Decimal(hours * 20000)
        
        self.save()
    
    def __str__(self):
        status_text = "Đang đỗ" if self.status == 'ACTIVE' else f"Đã ra ({self.duration_minutes}p)"
        return f"{self.license_plate} - {status_text}"
