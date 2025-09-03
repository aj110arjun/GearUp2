# transactions/urls.py
from django.urls import path
from .views import admin_transaction_list

urlpatterns = [
    path('admin/transactions/', admin_transaction_list, name='admin_transaction_list'),
]
