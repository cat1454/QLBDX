from django.urls import path

from parking import api, api_views
from . import views
from django.conf import settings
from django.conf.urls.static import static
urlpatterns = [
    path('', views.home, name='home'),
    path('login/', views.login_view, name='login'),
    # path('register/', views.register_view, name='register'),  # Disabled - Only admin can add users
    path('logout/', views.logout_view, name='logout'),
 
 # 🔹 Các dashboard riêng
    path('dashboard_admin/', views.dashboard_admin, name='dashboard_admin'),
    path('add_staff/', views.add_staff, name='add_staff'),
    
    path('dashboard_user/', views.dashboard_user, name='dashboard_user'),
    path('payment_cashier/', views.payment_cashier, name='payment_cashier'),

    path('parking_history/', views.parking_history, name='parking_history'),
    
   # API endpoints - Video & Detection
    path('video_feed/<str:src>', views.video_feed, name='video_feed'),
    path('api/stream/<str:src>', views.receive_stream, name='receive_stream'),
    path('api/upload/', views.upload_license_plate, name='upload_license_plate'),
    path('api/latest_detections/', views.latest_detections, name='latest_detections'),
    path('api/toggle_barrier/', views.toggle_barrier, name='toggle_barrier'),
    
    # API endpoints - Thống kê doanh thu
    path('api/revenue/stats/', api_views.revenue_statistics, name='revenue_statistics'),
    path('api/revenue/daily/', api_views.revenue_by_day, name='revenue_by_day'),
    path('api/revenue/monthly/', api_views.revenue_by_month, name='revenue_by_month'),
    
    # API endpoints - Quản lý giao dịch
    path('api/sessions/active/', api_views.get_active_sessions, name='get_active_sessions'),
    path('api/sessions/<int:session_id>/', api_views.get_session_detail, name='get_session_detail'),
    path('api/sessions/<int:session_id>/pay/', api_views.mark_session_paid, name='mark_session_paid'),
    path('api/sessions/unpaid/', api_views.get_unpaid_sessions, name='get_unpaid_sessions'),
    path('api/sessions/history/', api_views.get_transaction_history, name='get_transaction_history'),
   
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)