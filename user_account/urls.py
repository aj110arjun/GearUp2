from django.urls import path
from . import views


urlpatterns = [
    path('info/', views.account_info, name="account_info"),
    path('edit/', views.edit_profile, name="edit_profile"),
    path('verify/email/otp/', views.verify_email_otp, name="verify_email_otp"),
]
