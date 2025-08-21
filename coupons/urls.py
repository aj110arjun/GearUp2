from django.urls import path
from . import views

urlpatterns = [
    path("apply/", views.apply_coupon, name="apply_coupon"),
    path("remove/", views.remove_coupon, name="remove_coupon"),
    path("coupon/list/", views.admin_coupon_list, name="admin_coupon_list"),
    path("coupons/add/", views.admin_coupon_add, name="admin_coupon_add"),
    path("coupons/edit/<int:id>/", views.admin_coupon_edit, name="admin_coupon_edit"),
    path("coupons/delete/<int:id>/", views.admin_coupon_delete, name="admin_coupon_delete"),

]
