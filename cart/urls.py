from django.urls import path
from . import views


urlpatterns = [
    path("list/", views.cart_view, name="cart_view"),
    path("add/<int:variant_id>/", views.add_to_cart, name="add_to_cart"),
    path("update/<int:item_id>/", views.update_cart, name="update_cart"),
    path("remove/<int:item_id>/", views.remove_from_cart, name="remove_from_cart"),
    path('update/variant/<int:item_id>/', views.update_variant, name='update_variant'),
    path("toggle/cart/", views.toggle_cart, name="toggle_cart"),



]
