# orders/urls.py
from django.urls import path
from . import views

urlpatterns = [
    path("checkout/", views.checkout, name="checkout"),
    path("list/", views.order_list, name="order_list"),
    path("orders/<uuid:order_id>/", views.order_detail, name="order_detail"),
    path('admin/list/', views.admin_order_list, name='admin_order_list'),
    path('admin/<uuid:order_id>/', views.admin_order_detail, name='admin_order_detail'),
    path('admin/item/<uuid:item_id>/update-status/', views.admin_update_order_item_status, name='admin_update_order_item_status'),
    path('complete/<uuid:order_id>', views.order_complete, name='order_complete'),
    path('admin/cancellation-requests/', views.admin_cancellation_requests, name='admin_cancellation_requests'),
    path('admin/cancellation/<uuid:item_id>/<str:action>/', views.admin_approve_reject_cancellation, name='admin_approve_reject_cancellation'),
    path('order-item/<uuid:item_id>/request-cancel/', views.request_cancel_order_item, name='request_cancel_order_item'),
    path("orders/cancellation/<uuid:item_id>/view/", views.admin_cancellation_request_view, name="admin_cancellation_request_view"),
    path("orders/item/<uuid:item_id>/return/", views.request_return_order_item, name="request_return_order_item"),
    path("admin/orders/returns/", views.admin_return_requests, name="admin_return_requests"),
    path("admin/orders/returns/<uuid:item_id>/<str:action>/", views.admin_approve_reject_return, name="admin_approve_reject_return"),
    path("track/", views.track_order_search, name="track_order_search"),




]
