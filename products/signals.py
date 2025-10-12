from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.db.models import Avg, Count
from .models import Review, Product

def update_product_rating(product_id):
    reviews = Review.objects.filter(product_id=product_id, is_approved=True)
    agg = reviews.aggregate(avg=Avg("rating"), cnt=Count("id"))
    Product.objects.filter(id=product_id).update(
        avg_rating=round(agg["avg"] or 0, 2),
        rating_count=agg["cnt"] or 0
    )

@receiver(post_save, sender=Review)
def review_created_or_updated(sender, instance, **kwargs):
    update_product_rating(instance.product_id)

@receiver(post_delete, sender=Review)
def review_deleted(sender, instance, **kwargs):
    update_product_rating(instance.product_id)