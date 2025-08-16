from django.urls import path
from . import views


urlpatterns = [
    path('list/', views.address_list, name="address_list"),
    path('<int:pk>/delete/', views.delete_address, name="delete_address"),
    path('add/', views.add_address, name="add_address"),
    path('<int:pk>/edit/', views.edit_address, name="edit_address"),
]