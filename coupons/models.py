from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils import timezone

class Coupon(models.Model):
    code = models.CharField(max_length=50, unique=True)
    discount_percentage = models.DecimalField(
        max_digits=5, 
        decimal_places=2, 
        validators=[MinValueValidator(0), MaxValueValidator(100)]
    )
    usage_limit = models.PositiveIntegerField(null=True, blank=True)
    used_count = models.PositiveIntegerField(default=0)
    valid_from = models.DateTimeField()
    valid_until = models.DateTimeField()
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"{self.code} - {self.discount_percentage}%"
    
    def is_valid(self, order_amount=0):
        """Check if coupon is valid for use"""
        now = timezone.now()
        
        if not self.is_active:
            return False, "Coupon is not active"
        
        if now < self.valid_from:
            return False, "Coupon is not yet valid"
        
        if now > self.valid_until:
            return False, "Coupon has expired"
        
        if self.usage_limit and self.used_count >= self.usage_limit:
            return False, "Coupon usage limit reached"
        
        return True, "Valid coupon"
    
    def calculate_discount(self, order_amount):
        """Calculate discount amount based on order total"""
        is_valid, message = self.is_valid(order_amount)
        if not is_valid:
            return 0, message
        
        # Calculate percentage discount
        discount = (order_amount * self.discount_percentage) / 100
        
        # Apply maximum discount limit if set
        
        
        return discount, "Discount calculated successfully"
    
    def apply_to_order(self, order_amount, user, order_id):
        """Apply coupon to an order and track usage"""
        discount_amount, message = self.calculate_discount(order_amount)
        
        if discount_amount == 0:
            return False, message
        
        # Check if coupon has already been used for this order
        if CouponUsage.objects.filter(coupon=self, order_id=order_id).exists():
            return False, "Coupon already used for this order"
        
        # Create usage record
        CouponUsage.objects.create(
            coupon=self,
            user=user,
            order_id=order_id,
            discount_amount=discount_amount
        )
        
        # Update usage count
        self.used_count += 1
        self.save()
        
        final_amount = order_amount - discount_amount
        return True, {
            'discount_amount': discount_amount,
            'final_amount': final_amount,
            'message': f"Successfully applied {self.discount_percentage}% discount"
        }


class CouponUsage(models.Model):
    coupon = models.ForeignKey(Coupon, on_delete=models.CASCADE, related_name='usage_history')
    user = models.ForeignKey('auth.User', on_delete=models.CASCADE)
    order_id = models.PositiveIntegerField()
    discount_amount = models.DecimalField(max_digits=10, decimal_places=2)
    used_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ['coupon', 'order_id']
    
    def __str__(self):
        return f"{self.coupon.code} used on order #{self.order_id}"