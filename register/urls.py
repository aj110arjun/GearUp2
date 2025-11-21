from django.urls import path
from . import views


urlpatterns = [
    path('login/', views.user_login, name='login'),
    path('signup/', views.user_signup, name='signup'),
    path('logout/', views.logout_view, name='logout'),
    path('verify/otp/', views.verify_otp, name='verify_otp'),
    path('forgot-password/', views.forgot_password, name='forgot_password'),
    path('validate-email/', views.validate_user_email, name='validate_user_email'),
    path('reset-password/', views.reset_password, name='reset_password'),
    path("resend-otp/", views.resend_otp, name="resend_otp"),
    
    path('custom/admin/users/', views.user_list, name='user_list'),
    path('custom/admin/users/<int:user_id>', views.toggle_user_status, name='toggle_user_status'),
    path('custom/admin/login/', views.admin_login, name='admin_login'),
    path('custom/admin/logout/', views.admin_logout_view, name='admin_logout'),
    
]
