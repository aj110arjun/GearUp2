from django.urls import path
from . import views

urlpatterns = [
    # Product Offers
    path("custom/admin/offers/products/", views.admin_product_offers, name="admin_product_offers"),
    path("custom/admin/offers/products/add/", views.admin_add_product_offer, name="admin_add_product_offer"),
    path("custom/admin/offers/products/delete/<int:offer_id>/", views.admin_delete_product_offer, name="admin_delete_product_offer"),
    path("custom/admin/offers/products/edit/<int:product_id>/", views.admin_product_offer_edit, name="admin_product_offer_edit"),

    # Category Offers
    path("custom/admin/offers/categories/", views.admin_category_offers, name="admin_category_offers"),
    path("custom/admin/offers/categories/add/", views.admin_add_category_offer, name="admin_add_category_offer"),
    path("custom/admin/offers/categories/edit/<uuid:category_id>", views.admin_category_offer_edit, name="admin_category_offer_edit"),
    path("custom/admin/offers/categories/delete/<int:offer_id>/", views.admin_delete_category_offer, name="admin_delete_category_offer"),
]
