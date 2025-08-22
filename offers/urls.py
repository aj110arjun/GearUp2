from django.urls import path
from . import views

urlpatterns = [
    # Product Offers
    path("offers/products/", views.admin_product_offers, name="admin_product_offers"),
    path("offers/products/add/", views.admin_add_product_offer, name="admin_add_product_offer"),
    path("offers/products/delete/<int:offer_id>/", views.admin_delete_product_offer, name="admin_delete_product_offer"),
    path("offers/products/edit/<uuid:product_id>/", views.admin_product_offer_edit, name="admin_product_offer_edit"),

    # Category Offers
    path("offers/categories/", views.admin_category_offers, name="admin_category_offers"),
    path("offers/categories/add/", views.admin_add_category_offer, name="admin_add_category_offer"),
    path("offers/categories/edit/<uuid:category_id>", views.admin_category_offer_edit, name="admin_category_offer_edit"),
    path("offers/categories/delete/<int:offer_id>/", views.admin_delete_category_offer, name="admin_delete_category_offer"),
]
