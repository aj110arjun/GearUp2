from django.urls import path
from . import views


urlpatterns = [
    path('list/', views.product_list, name='product_list'),
    path("<uuid:product_id>/", views.product_detail, name="product_detail"),
    
    path('custom/admin/add/', views.admin_product_add, name='product_add'),
    path('custom/admin/list/', views.admin_product_list, name='admin_product_list'),
    path('custom/admin/categories/', views.category_list, name='category_list'),
    path('custom/admin/categories/add/', views.category_add, name='category_add'),
    path('custom/admin/categories/edit/<uuid:id>/', views.category_edit, name='category_edit'),
    path('custom/admin/details/<uuid:product_id>/', views.admin_product_detail, name='admin_product_detail'),
    path('custom/admin/edit/<uuid:product_id>/', views.admin_product_edit, name='admin_product_edit'),
    path('custom/admin/products/<uuid:product_id>/toggle-status/', views.toggle_product_status, name='admin_product_toggle_status'),
    path('admin/product/<int:product_id>/variant/add/', views.admin_variant_add, name='admin_variant_add'),
    path('admin/variant/<int:variant_id>/edit/', views.admin_variant_edit, name='admin_variant_edit'),
    path('admin/variant/<int:variant_id>/delete/', views.admin_variant_delete, name='admin_variant_delete'),
    path('admin/product/<int:product_id>/images/add/', views.admin_image_add, name='admin_image_add'),


    
]
