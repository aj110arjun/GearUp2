from django.db import models
from django.contrib.auth.models import User
from products.models import ProductVariant

class CartItem(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="cart_items")
    variant = models.ForeignKey(ProductVariant, on_delete=models.CASCADE, related_name="in_carts")
    quantity = models.PositiveIntegerField(default=1)
    added_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("user", "variant")

    def subtotal(self):
        return self.quantity * self.variant.price

    def __str__(self):
        return f"{self.user.username} → {self.variant.product.name} ({self.variant.color}/{self.variant.size})"
