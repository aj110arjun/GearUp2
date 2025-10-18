from django.db import models
from django.utils import timezone
from django.contrib.auth.models import User
from products.models import Product

class Coupon(models.Model):
    code = models.CharField(max_length=50, unique=True)
    discount_value = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        help_text="Fixed discount amount in currency (e.g., 200.00)",
        default=0
    )
    active = models.BooleanField(default=True)
    valid_from = models.DateTimeField()
    valid_to = models.DateTimeField()
    usage_limit_per_user = models.PositiveIntegerField(default=1, help_text="Max times a user can use this coupon")
    usage_limit_total = models.PositiveIntegerField(default=0, help_text="Max total uses (0 = unlimited)")
    total_uses = models.PositiveIntegerField(default=0, editable=False)
    products = models.ManyToManyField(Product, blank=True, related_name='coupons')

    users_used = models.ManyToManyField(User, through='CouponRedemption', related_name='coupons_used', blank=True)

    class Meta:
        ordering = ['-valid_to']

    def is_valid(self):
        """Check if coupon is active and within its valid period."""
        now = timezone.now()
        if not self.active or now < self.valid_from or now > self.valid_to:
            return False
        if self.usage_limit_total and self.total_uses >= self.usage_limit_total:
            return False
        return True

    def can_user_use(self, user):
        """Check if user can still use this coupon."""
        if not self.is_valid():
            return False
        user_usage_count = CouponRedemption.objects.filter(user=user, coupon=self, refunded=False).count()
        return user_usage_count < self.usage_limit_per_user

    def increment_usage(self, user, order):
        """Record usage of coupon."""
        redemption = CouponRedemption.objects.create(user=user, coupon=self, order=order)
        self.total_uses += 1
        self.save()
        return redemption

    def __str__(self):
        return f"{self.code} - ₹{self.discount_value}"


class CouponRedemption(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    coupon = models.ForeignKey(Coupon, on_delete=models.CASCADE)
    order = models.ForeignKey('orders.Order', on_delete=models.CASCADE, related_name='coupon_redemptions')
    redeemed_at = models.DateTimeField(auto_now_add=True)
    refunded = models.BooleanField(default=False)

    class Meta:
        unique_together = ('user', 'coupon', 'order')

    def __str__(self):
        return f"{self.user} redeemed {self.coupon.code} on order {self.order_id}"
