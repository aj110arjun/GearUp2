from django.urls import path
from . import views


urlpatterns = [
    path('list/', views.product_list, name='product_list'),
    path('admin/list/', views.admin_product_list, name='admin_product_list'),
]
