import uuid

from django.db import models
from datetime import date


class Category(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    parent = models.ForeignKey(
        'self', on_delete=models.CASCADE, null=True, blank=True, related_name="subcategories"
    )

    def __str__(self):
        return self.name

class Product(models.Model):
    name = models.CharField(max_length=255)
    product_id = models.UUIDField(default=uuid.uuid4, editable=False, unique=True, null=True, blank=True)
    category = models.ForeignKey(
        Category, on_delete=models.SET_NULL, null=True, blank=True, related_name="products"
    )
    description = models.TextField(blank=True)
    brand = models.CharField(max_length=100, blank=True)
    image = models.ImageField(upload_to='products/', blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)
    
    def get_best_offer(self):
        today = date.today()
        product_offer = ProductOffer.objects.filter(
            product=self,
            active=True,
            start_date__lte=today,
            end_date__gte=today
        ).first()

        category_offer = CategoryOffer.objects.filter(
            category=self.category,
            active=True,
            start_date__lte=today,
            end_date__gte=today
        ).first()

        # Decide which offer to apply
        product_discount = product_offer.discount_percent if product_offer else 0
        category_discount = category_offer.discount_percent if category_offer else 0

        best_discount = max(product_discount, category_discount)
        return best_discount
    
    def total_stock(self):
        """Return total stock based on variants."""
        return sum(variant.stock for variant in self.variants.all())

    def __str__(self):
        return self.name

class ProductVariant(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="variants")
    color = models.CharField(max_length=255)
    size = models.CharField(max_length=255)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    stock = models.PositiveIntegerField(default=0)
    
    def get_discounted_price(self):
        best_discount = self.product.get_best_offer()
        if best_discount:
            discounted_price = self.price - (self.price * best_discount / 100)
            return round(discounted_price, 2)
        return self.price

    def __str__(self):
        return f"{self.product.name}"
    
class ProductImage(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="images")
    image = models.ImageField(upload_to="products/additional/")
    alt_text = models.CharField(max_length=255, blank=True)

    def __str__(self):
        return f"Image for {self.product.name}"
    
class ProductOffer(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    discount_percent = models.PositiveIntegerField()  # e.g., 20 for 20%
    active = models.BooleanField(default=True)
    start_date = models.DateField()
    end_date = models.DateField()
    
    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["product"], name="unique_product_offer")
        ]

    def __str__(self):
        return f"{self.discount_percent}% off on {self.product.name}"
    
class CategoryOffer(models.Model):
    category = models.ForeignKey(Category, on_delete=models.CASCADE)
    discount_percent = models.PositiveIntegerField()
    active = models.BooleanField(default=True)
    start_date = models.DateField()
    end_date = models.DateField()

    def __str__(self):
        return f"{self.discount_percent}% off on {self.category.name}"
