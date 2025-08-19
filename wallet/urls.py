from django.urls import path
from . import views


urlpatterns = [
    path("view/", views.user_wallet, name="user_wallet"),
]
