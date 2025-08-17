# orders/urls.py
from django.urls import path
from . import views

urlpatterns = [
    path("checkout/", views.checkout, name="checkout"),
    path("list/", views.order_list, name="order_list"),
    path("<int:order_id>/", views.order_detail, name="order_detail"),
    path('admin/list/', views.admin_order_list, name='admin_order_list'),
    path('admin/<int:order_id>/', views.admin_order_detail, name='admin_order_detail'),
    path('admin/item/<int:item_id>/update-status/', views.admin_update_order_item_status, name='admin_update_order_item_status'),
    path('complete/<int:order_id>', views.order_complete, name='order_complete'),
    path('admin/cancellation-requests/', views.admin_cancellation_requests, name='admin_cancellation_requests'),
    path('admin/cancellation/<int:item_id>/<str:action>/', views.admin_approve_reject_cancellation, name='admin_approve_reject_cancellation'),
    path('order-item/<int:item_id>/request-cancel/', views.request_cancel_order_item, name='request_cancel_order_item'),
    path("orders/cancellation/<int:item_id>/view/", views.admin_cancellation_request_view, name="admin_cancellation_request_view"),
    path("orders/item/<int:item_id>/return/", views.request_return_order_item, name="request_return_order_item"),
    path("admin/orders/returns/", views.admin_return_requests, name="admin_return_requests"),
    path("admin/orders/returns/<int:item_id>/<str:action>/", views.admin_approve_reject_return, name="admin_approve_reject_return"),




]
