from django.shortcuts import redirect
from django.contrib import messages

class RoleMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.user.is_authenticated:
            if 'dashboard' in request.path:
                user_role = request.user.profile.role.lower()
                if user_role not in request.path:
                    messages.warning(request, 'Bạn không có quyền truy cập trang này.')
                    if user_role == 'admin':
                        return redirect('dashboard_admin')
                    elif user_role == 'user':
                        return redirect('dashboard_user')
                    else:
                        return redirect('dashboard_customer')
        
        response = self.get_response(request)
        return response