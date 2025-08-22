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

    @property
    def subtotal(self):
        # ✅ Apply best offer price if available
        discount_percent = self.variant.product.get_best_offer()
        if discount_percent > 0:
            price = self.variant.get_discounted_price()
        else:
            price = self.variant.price
        return self.quantity * price

    def __str__(self):
        return f"{self.user.username} → {self.variant.product.name} ({self.variant.color}/{self.variant.size})"
