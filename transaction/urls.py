# transactions/urls.py
from django.urls import path
from . import views

urlpatterns = [
    path('custom/admin/transactions/', views.admin_transaction_list, name='admin_transaction_list'),
    path('custom/admin/transactions/detail/<str:transaction_id>', views.admin_transaction_detail, name='admin_transaction_detail'),
    
]
