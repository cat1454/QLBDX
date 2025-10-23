from django.urls import path
from . import views

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

]
