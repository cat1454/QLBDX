import os
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'smartparking.settings')
django.setup()

from django.contrib.auth.models import User

username = 'tuanhtai'
password = 'maiiu36@'
email = ''

# Kiểm tra nếu user đã tồn tại
try:
    user = User.objects.get(username=username)
    print(f'⚠️  User "{username}" đã tồn tại. Đang cập nhật...')
    
    # Cập nhật password và set làm superuser
    user.set_password(password)
    user.is_superuser = True
    user.is_staff = True
    user.save()
    
    print(f'✅ Đã cập nhật tài khoản:')
    print(f'   Username: {user.username}')
    print(f'   Superuser: {user.is_superuser}')
    print(f'   Staff: {user.is_staff}')
    print(f'   Password: Đã cập nhật')
    
except User.DoesNotExist:
    # Tạo superuser mới
    user = User.objects.create_superuser(
        username=username,
        password=password,
        email=email
    )
    
    print(f'✅ Đã tạo tài khoản superuser:')
    print(f'   Username: {user.username}')
    print(f'   Superuser: {user.is_superuser}')
    print(f'   Staff: {user.is_staff}')
    print(f'   ID: {user.id}')
