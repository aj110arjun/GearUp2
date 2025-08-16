# orders/urls.py
from django.urls import path
from . import views

urlpatterns = [
    path("checkout/", views.checkout, name="checkout"),
    path("list/", views.order_list, name="order_list"),
    path("<int:order_id>/", views.order_detail, name="order_detail"),
    
    path("admin/list/", views.admin_order_list, name="admin_order_list"),
    path("admin/<int:order_id>/", views.admin_order_detail, name="admin_order_detail"),
    path("admin/<int:order_id>/status/<str:status>/", views.update_order_status, name="update_order_status"),
]
