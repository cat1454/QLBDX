from django.db import models
from django.contrib.auth.models import User
from decimal import Decimal

class Profile(models.Model):
    ROLE_CHOICES = [
        ('Admin', 'Admin'),
        ('User', 'User'),
        ('Customer', 'Customer'),
    ]

    user = models.OneToOneField(User, on_delete=models.CASCADE)
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='Customer')
    wallet = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    avatar = models.ImageField(upload_to='avatars/', default='avatars/default.png')
    license_plate = models.CharField(max_length=20, blank=True, null=True, unique=True)
    e_wallet = models.CharField(max_length=50, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.username} - {self.role}"

    def add_funds(self, amount):
        """Thêm tiền vào ví"""
        self.wallet += Decimal(amount)
        self.save()
        Transaction.objects.create(
            profile=self,
            amount=amount,
            type='DEPOSIT',
            note='Nạp tiền vào ví'
        )

    def deduct_funds(self, amount, note=''):
        """Trừ tiền từ ví"""
        if self.wallet >= Decimal(amount):
            self.wallet -= Decimal(amount)
            self.save()
            Transaction.objects.create(
                profile=self,
                amount=-amount,
                type='PAYMENT',
                note=note
            )
            return True
        return False

class ParkingRecord(models.Model):
    STATUS_CHOICES = [
        ('PARKING', 'Đang đỗ'),
        ('COMPLETED', 'Đã rời đi'),
        ('CANCELLED', 'Đã hủy'),
    ]

    profile = models.ForeignKey(Profile, on_delete=models.CASCADE)
    spot_number = models.IntegerField()
    entry_time = models.DateTimeField(auto_now_add=True)
    exit_time = models.DateTimeField(null=True, blank=True)
    duration = models.DurationField(null=True, blank=True)
    fee = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PARKING')
    license_plate = models.CharField(max_length=20)
    paid = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.license_plate} - Spot {self.spot_number}"

    def complete_parking(self):
        """Kết thúc phiên gửi xe và tính phí"""
        from django.utils import timezone
        import math

        if self.status == 'PARKING':
            self.exit_time = timezone.now()
            self.duration = self.exit_time - self.entry_time
            
            # Tính phí: 20,000 VNĐ/giờ, làm tròn lên
            hours = math.ceil(self.duration.total_seconds() / 3600)
            self.fee = Decimal(hours * 20000)
            
            self.status = 'COMPLETED'
            self.save()

            # Tự động trừ tiền nếu có đủ số dư
            if self.profile.deduct_funds(self.fee, f'Thanh toán phí đỗ xe - {self.spot_number}'):
                self.paid = True
                self.save()

class Transaction(models.Model):
    TYPE_CHOICES = [
        ('DEPOSIT', 'Nạp tiền'),
        ('PAYMENT', 'Thanh toán'),
        ('REFUND', 'Hoàn tiền'),
    ]

    profile = models.ForeignKey(Profile, on_delete=models.CASCADE)
    timestamp = models.DateTimeField(auto_now_add=True)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    type = models.CharField(max_length=20, choices=TYPE_CHOICES)
    note = models.TextField(blank=True)
    balance = models.DecimalField(max_digits=10, decimal_places=2)

    def save(self, *args, **kwargs):
        # Cập nhật số dư sau giao dịch
        if not self.id:  # Chỉ cập nhật khi tạo mới
            self.balance = self.profile.wallet
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.profile.user.username} - {self.type} - {self.amount}"
