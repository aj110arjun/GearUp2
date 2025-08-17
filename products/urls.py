from django.urls import path
from . import views


urlpatterns = [
    path('list/', views.product_list, name='product_list'),
    path("<uuid:product_id>/", views.product_detail, name="product_detail"),
    
    path('add/', views.admin_product_add, name='product_add'),
    path('admin/list/', views.admin_product_list, name='admin_product_list'),
    path('categories/', views.category_list, name='category_list'),
    path('categories/add/', views.category_add, name='category_add'),
    path('categories/edit/<uuid:id>/', views.category_edit, name='category_edit'),
    path('categories/delete/<uuid:id>/', views.category_delete, name='category_delete'),
    path('details/<uuid:product_id>/', views.admin_product_detail, name='admin_product_detail'),
    path('edit/<uuid:product_id>/', views.admin_product_edit, name='admin_product_edit'),
    path('admin/products/<uuid:product_id>/toggle-status/', views.toggle_product_status, name='admin_product_toggle_status'),
    
]
