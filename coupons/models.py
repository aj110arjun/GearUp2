from django.db import models
from django.utils import timezone
from django.contrib.auth.models import User

class Coupon(models.Model):
    code = models.CharField(max_length=50, unique=True)
    discount = models.PositiveIntegerField(help_text="Percentage discount (e.g. 10 for 10%)")
    active = models.BooleanField(default=True)
    valid_from = models.DateTimeField()
    valid_to = models.DateTimeField()
    usage_limit = models.PositiveIntegerField(default=1, help_text="How many times a user can use this coupon")
    used_by = models.ManyToManyField(User, blank=True, related_name="used_coupons")
    total_uses = models.PositiveIntegerField(default=0)

    def can_user_use(self, user):
        """Check if this user can still use the coupon."""
        user_uses = CouponUsage.objects.filter(user=user, coupon=self, refunded=False).count()
        return self.is_valid() and user_uses < self.usage_limit

    def is_valid(self):
        now = timezone.now()
        return self.active and self.valid_from <= now <= self.valid_to

    def __str__(self):
        return self.code

class CouponUsage(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    coupon = models.ForeignKey(Coupon, on_delete=models.CASCADE)
    order = models.ForeignKey('orders.Order', on_delete=models.CASCADE, related_name="coupon_usages")
    used_at = models.DateTimeField(auto_now_add=True)
    refunded = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.user} used {self.coupon.code} on order {self.order_id}"
