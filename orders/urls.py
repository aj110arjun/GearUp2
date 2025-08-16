# orders/urls.py
from django.urls import path
from . import views

urlpatterns = [
    path("checkout/", views.checkout, name="checkout"),
    path("list/", views.order_list, name="order_list"),
    path("<int:order_id>/", views.order_detail, name="order_detail"),
]
