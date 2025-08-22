from django.contrib import admin
from .models import Product, ProductVariant, Category, ProductImage, ProductOffer, CategoryOffer


admin.site.register(Product)
admin.site.register(ProductVariant)
admin.site.register(Category)
admin.site.register(ProductImage)

@admin.register(ProductOffer)
class ProductOfferAdmin(admin.ModelAdmin):
    list_display = ("product", "discount_percent", "active", "start_date", "end_date")

@admin.register(CategoryOffer)
class CategoryOfferAdmin(admin.ModelAdmin):
    list_display = ("category", "discount_percent", "active", "start_date", "end_date")

