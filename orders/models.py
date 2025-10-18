import uuid
from django.db import models
from django.contrib.auth.models import User
from products.models import ProductVariant
from address.models import Address
from coupons.models import Coupon
from django.utils.timezone import now

def generate_order_code():
    """
    Example: ORD20251017-AB12CD
    Date prefix + 6-char random hex
    """
    return f"ORD{now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}"

class Order(models.Model):
    PAYMENT_METHODS = [
        ("COD", "Cash on Delivery"),
        ("ONLINE", "Online Payment"),
        ("WALLET", "Wallet")
    ]

    ORDER_STATUS = [
        ("Pending", "Pending"),
        ("Processing", "Processing"),
        ("Shipped", "Shipped"),
        ("Out For Delivery", "Out For Delivery"),
        ("Delivered", "Delivered"),
        ("Cancelled", "Cancelled"),
        ("Returned", "Returned"),
    ]

    id = models.BigAutoField(primary_key=True)
    order_id = models.UUIDField(default=uuid.uuid4, editable=False, unique=True, null=True, blank=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="orders")
    product = models.ForeignKey(ProductVariant, on_delete=models.SET_NULL, null=True)
    address = models.ForeignKey(Address, on_delete=models.SET_NULL, null=True, blank=True)

    quantity = models.PositiveIntegerField(default=1)
    price = models.DecimalField(max_digits=10, decimal_places=2, default=0)  # unit price
    total_price = models.DecimalField(max_digits=10, decimal_places=2)  # price * quantity
    tax = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    discount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    coupon = models.ForeignKey(Coupon, null=True, blank=True, on_delete=models.SET_NULL)
    coupon_refunded = models.BooleanField(default=False)

    payment_method = models.CharField(max_length=20, choices=PAYMENT_METHODS, default="COD")
    payment_status = models.CharField(
        max_length=20,
        choices=[("Pending", "Pending"), ("Paid", "Paid"), ("Failed", "Failed")],
        default="Pending"
    )

    order_status = models.CharField(
        max_length=20,
        choices=ORDER_STATUS,
        default="Pending"
    )

    # Razorpay fields
    razorpay_order_id = models.CharField(max_length=255, blank=True, null=True)
    razorpay_payment_id = models.CharField(max_length=255, blank=True, null=True)
    razorpay_signature = models.CharField(max_length=255, blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)
    order_code = models.CharField(max_length=20, unique=True, editable=False, default=generate_order_code)
    
    cancellation_requested = models.BooleanField(default=False)
    cancellation_reason = models.TextField(blank=True, null=True)
    cancellation_approved = models.BooleanField(null=True, blank=True)

    def save(self, *args, **kwargs):
        if not self.order_code:
            self.order_code = generate_order_code()
        # calculate total price automatically
        self.total_price = self.price * self.quantity
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Order {self.order_code} - {self.product.product.name} x{self.quantity} by {self.user.username}"
