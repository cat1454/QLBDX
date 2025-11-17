from django.urls import path

from parking import api
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

    path('parking_history/', views.parking_history, name='parking_history'),
    
   # API endpoints
    path('video_feed/<str:src>', views.video_feed, name='video_feed'),
    path('api/stream/<str:src>', views.receive_stream, name='receive_stream'),
    path('api/upload/', views.upload_license_plate, name='upload_license_plate'),
    path('api/latest_detections/', views.latest_detections, name='latest_detections'),
    path('api/toggle_barrier/', views.toggle_barrier, name='toggle_barrier'),
   
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)