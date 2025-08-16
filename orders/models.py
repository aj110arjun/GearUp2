# orders/models.py
from django.db import models
from django.contrib.auth.models import User
from products.models import ProductVariant
from address.models import Address  # if you already have address management

class Order(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="orders")
    address = models.ForeignKey(Address, on_delete=models.SET_NULL, null=True, blank=True)
    total_price = models.DecimalField(max_digits=10, decimal_places=2)
    created_at = models.DateTimeField(auto_now_add=True)

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
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="items")
    variant = models.ForeignKey(ProductVariant, on_delete=models.SET_NULL, null=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    quantity = models.PositiveIntegerField(default=1)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    
    cancellation_requested = models.BooleanField(default=False)
    cancellation_reason = models.TextField(blank=True, null=True)
    cancellation_approved = models.BooleanField(null=True)

    def subtotal(self):
        return self.price * self.quantity

    def __str__(self):
        return f"{self.variant.product.name} ({self.variant.color}/{self.variant.size}) x{self.quantity}"
