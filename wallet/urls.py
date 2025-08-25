from django.urls import path
from . import views


urlpatterns = [
    path("view/", views.user_wallet, name="user_wallet"),
    path("wallet/payment_success/", views.wallet_payment_success, name="payment_success"),
    path("wallet/create_order/", views.create_order, name="create_order"),
]
