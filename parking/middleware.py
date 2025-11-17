from django.shortcuts import redirect
from django.contrib import messages

class RoleMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.user.is_authenticated:
            if 'dashboard' in request.path:
                # Sử dụng is_superuser thay vì profile.role
                if request.user.is_superuser and 'dashboard_admin' not in request.path:
                    return redirect('dashboard_admin')
                elif not request.user.is_superuser and 'dashboard_user' not in request.path and 'dashboard' in request.path:
                    return redirect('dashboard_user')
        
        response = self.get_response(request)
        return response