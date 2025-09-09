# orders/urls.py
from django.urls import path
from . import views

urlpatterns = [
    
    # User View
    path("checkout/", views.checkout, name="checkout"),
    path("list/", views.order_list, name="order_list"),
    path("orders/<uuid:order_id>/", views.order_detail, name="order_detail"),
    path('complete/<uuid:order_id>', views.order_complete, name='order_complete'),
    path('order-item/<uuid:item_id>/request-cancel/', views.request_cancel_order_item, name='request_cancel_order_item'),
    path("orders/item/<uuid:item_id>/return/", views.request_return_order_item, name="request_return_order_item"),
    path("track/", views.track_order_search, name="track_order_search"),
    path("orders/<str:order_code>/invoice/", views.download_invoice, name="download_invoice"),
    path("order/cancel/<uuid:item_id>/", views.cancel_order_item_page, name="cancel_order_item_page"),
    path("order/return/<uuid:item_id>/", views.return_order_item_page, name="return_order_item_page"),
    path("pay/<uuid:order_id>/", views.start_payment, name="start_payment"),
    path("payment/success/<uuid:order_id>/", views.payment_success, name="payment_success"),
    path("success/<uuid:order_id>/", views.order_success, name="order_success"), 
    path("failure/<uuid:order_id>/", views.payment_failed, name="payment_failed"),
    path('payment/retry/<uuid:order_id>/', views.retry_payment, name='retry_payment'),

    # Admin View
    path('custom/admin/list/', views.admin_order_list, name='admin_order_list'),
    path('custom/admin/<uuid:order_id>/', views.admin_order_detail, name='admin_order_detail'),
    path('custom/admin/item/<uuid:item_id>/update-status/', views.admin_update_order_item_status, name='admin_update_order_item_status'),
    path('custom/admin/cancellation-requests/', views.admin_cancellation_requests, name='admin_cancellation_requests'),
    path('custom/admin/cancellation/<uuid:item_id>/<str:action>/', views.admin_approve_reject_cancellation, name='admin_approve_reject_cancellation'),
    path("custom/admin/orders/cancellation/<uuid:item_id>/view/", views.admin_cancellation_request_view, name="admin_cancellation_request_view"),
    path("custom/admin/orders/returns/", views.admin_return_requests, name="admin_return_requests"),
    path("custom/admin/orders/returns/<uuid:item_id>/<str:action>/", views.admin_approve_reject_return, name="admin_approve_reject_return"),
    path('custom/admin/return-reason/<uuid:item_id>/', views.admin_view_return_reason, name='admin_view_return_reason'),






]
