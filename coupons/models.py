from django.db import models
from django.utils import timezone

class Coupon(models.Model):
    code = models.CharField(max_length=50, unique=True)
    discount = models.PositiveIntegerField(help_text="Percentage discount (e.g. 10 for 10%)")
    active = models.BooleanField(default=True)
    valid_from = models.DateTimeField()
    valid_to = models.DateTimeField()
    min_purchase = models.DecimalField(max_digits=10, decimal_places=2,default=0)
    usage_limit = models.PositiveIntegerField(default=1, help_text="How many times a user can use this coupon")

    def is_valid(self):
        now = timezone.now()
        return self.active and self.valid_from <= now <= self.valid_to

    def __str__(self):
        return self.code
