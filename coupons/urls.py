from django.urls import path
from . import views

urlpatterns = [
    path('admin/coupons/', views.admin_coupon_list, name='admin_coupon_list'),
    path('admin/coupons/add/', views.admin_coupon_add, name='admin_coupon_add'),
    path('admin/coupons/edit/<int:coupon_id>/', views.admin_coupon_edit, name='admin_coupon_edit'),
    path('admin/coupons/delete/<int:coupon_id>/', views.admin_coupon_delete, name='admin_coupon_delete'),

    # ----------------- User URLs -----------------
    path('apply-coupon/', views.apply_coupon, name='apply_coupon'),
    path('remove-coupon/', views.remove_coupon, name='remove_coupon'),
]
