from django.urls import path
from . import views


urlpatterns = [
    path('login/', views.user_login, name='login'),
    path('signup/', views.user_signup, name='signup'),
    path('logout/', views.logout_view, name='logout'),
    path('verify/otp/', views.verify_otp, name='verify_otp'),
    path('forgot-password/', views.forgot_password, name='forgot_password'),
    path('reset-password/', views.reset_password, name='reset_password'),
    path("resend-otp/", views.resend_otp, name="resend_otp"),
    
    path('admin/login/', views.admin_login, name='admin_login'),
    path('admin/logout/', views.admin_logout_view, name='admin_logout'),
    
]
