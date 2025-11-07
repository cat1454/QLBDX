from django.urls import path

from parking import api
from . import views
from django.conf import settings
from django.conf.urls.static import static
urlpatterns = [
    path('', views.home, name='home'),
    path('login/', views.login_view, name='login'),
    path('register/', views.register_view, name='register'),
    path('logout/', views.logout_view, name='logout'),
 
 # 🔹 Các dashboard riêng
    path('dashboard_admin/', views.dashboard_admin, name='dashboard_admin'),
    
    path('dashboard_user/', views.dashboard_user, name='dashboard_user'),
    path('dashboard_customer/', views.dashboard_customer, name='dashboard_customer'),

    path('profile/', views.profile_view, name='profile'),
    path('edit_profile/', views.edit_profile, name='edit_profile'),

   
     path('parking_history/', views.parking_history, name='parking_history'),
    
   # API endpoints
    path('api/check-username/', api.check_username, name='api_check_username'),
    path('api/check-email/', api.check_email, name='api_check_email'),
    path('api/validate-registration/', api.validate_registration, name='api_validate_registration'),

] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)