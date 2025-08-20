import uuid

from django.db import models
from django.contrib.auth.models import User
from products.models import ProductVariant
from address.models import Address
from django.utils.timezone import now

def generate_order_code():
    """
    Example: ORD20250817-AB12CD
    Date prefix + 6-char random hex
    """
    return f"ORD{now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}"

class Order(models.Model):
    PAYMENT_METHODS = [
        ("COD", "Cash on Delivery"),
        ("ONLINE", "Online Payment"),
    ]
    id = models.BigAutoField(primary_key=True)
    order_id = models.UUIDField(default=uuid.uuid4, editable=False, unique=True, null=True, blank=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="orders")
    address = models.ForeignKey(Address, on_delete=models.SET_NULL, null=True, blank=True)
    total_price = models.DecimalField(max_digits=10, decimal_places=2)

    payment_method = models.CharField(max_length=20, choices=PAYMENT_METHODS, default="COD")
    payment_status = models.CharField(
        max_length=20,
        choices=[("Pending", "Pending"), ("Paid", "Paid"), ("Failed", "Failed")],
        default="Pending"
    )

    # Razorpay-specific fields
    razorpay_order_id = models.CharField(max_length=255, blank=True, null=True)
    razorpay_payment_id = models.CharField(max_length=255, blank=True, null=True)
    razorpay_signature = models.CharField(max_length=255, blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)
    order_code = models.CharField(max_length=20, unique=True, editable=False, default=generate_order_code)

    def save(self, *args, **kwargs):
        if not self.order_code:
            self.order_code = f"ORD-{self.created_at.strftime('%Y%m%d') if self.created_at else ''}-{uuid.uuid4().hex[:6].upper()}"
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Order {self.id} by {self.user.username}"


class OrderItem(models.Model):
    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("processing", "Processing"),
        ("shipped", "Shipped"),
        ("delivered", "Delivered"),
        ("cancelled", "Cancelled"),
    ]
    id = models.BigAutoField(primary_key=True)
    item_id = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="items")
    variant = models.ForeignKey(ProductVariant, on_delete=models.SET_NULL, null=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    quantity = models.PositiveIntegerField(default=1)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    refund_done = models.BooleanField(default=False)
    total_price = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    
    cancellation_requested = models.BooleanField(default=False)
    cancellation_reason = models.TextField(blank=True, null=True)
    cancellation_approved = models.BooleanField(null=True)
    
    return_requested = models.BooleanField(default=False)
    return_reason = models.TextField(blank=True, null=True)
    return_approved = models.BooleanField(null=True, blank=True)

    def subtotal(self):
        return self.price * self.quantity

    # def __str__(self):
    #     return f"{self.variant.product.name} ({self.variant.color}/{self.variant.size}) x{self.quantity}"
