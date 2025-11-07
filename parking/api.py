from django.http import JsonResponse
from django.contrib.auth.models import User
from django.views.decorators.http import require_http_methods
from .models import Profile

@require_http_methods(["GET"])
def check_username(request):
    """API kiểm tra username đã tồn tại chưa"""
    username = request.GET.get('username', '').strip()
    print(f"Checking username: {username}")  # Debug line
    if len(username) < 3:
        response = {
            'exists': True,
            'message': 'Tên đăng nhập phải có ít nhất 3 ký tự'
        }
        print(f"Response: {response}")  # Debug line
        return JsonResponse(response)
    exists = User.objects.filter(username__iexact=username).exists()
    response = {
        'exists': exists,
        'message': 'Tên đăng nhập đã tồn tại' if exists else 'Tên đăng nhập hợp lệ'
    }
    print(f"Response: {response}")  # Debug line
    return JsonResponse(response)

@require_http_methods(["GET"])
def check_email(request):
    """API kiểm tra email đã được sử dụng chưa"""
    email = request.GET.get('email', '').strip().lower()
    print(f"Checking email: {email}")  # Debug line
    exists = User.objects.filter(email__iexact=email).exists()
    response = {
        'exists': exists,
        'message': 'Email đã được sử dụng' if exists else 'Email hợp lệ'
    }
    print(f"Response: {response}")  # Debug line
    return JsonResponse(response)

@require_http_methods(["GET"])
def validate_registration(request):
    """API kiểm tra toàn bộ form đăng ký"""
    username = request.GET.get('username', '').strip()
    email = request.GET.get('email', '').strip().lower()
    
    errors = {}
    
    # Validate username
    if User.objects.filter(username__iexact=username).exists():
        errors['username'] = 'Tên đăng nhập đã tồn tại'
    elif len(username) < 3:
        errors['username'] = 'Tên đăng nhập phải có ít nhất 3 ký tự'
        
    # Validate email
    if User.objects.filter(email__iexact=email).exists():
        errors['email'] = 'Email đã được sử dụng'
        
    return JsonResponse({
        'valid': len(errors) == 0,
        'errors': errors
    })