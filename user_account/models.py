import datetime

from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone


class Profile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    profile_image = models.ImageField(upload_to='profiles/', blank=True, null=True, default='images/default.png')
    pending_email = models.EmailField(blank=True, null=True)
    email_otp = models.CharField(max_length=6, blank=True, null=True)
    otp_expiry = models.DateTimeField(blank=True, null=True)
    
    def set_otp(self, otp):
        self.email_otp = otp
        self.otp_expiry = timezone.now() + datetime.timedelta(minutes=10)
        self.save()

    def verify_otp(self, otp):
        return (
            self.email_otp == otp
            and self.otp_expiry
            and timezone.now() <= self.otp_expiry
        )
    
    def __str__(self):
        return self.user.username

