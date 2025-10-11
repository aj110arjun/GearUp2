from django.urls import path
from . import views


urlpatterns = [
    path("list/", views.wishlist_view, name="wishlist_view"),
    path("add/<int:pk>/", views.add_to_wishlist, name="add_to_wishlist"),
    path("remove/<int:pk>/", views.remove_from_wishlist, name="remove_from_wishlist"),
    path('wishlist/toggle/<int:product_id>/', views.toggle_wishlist, name='toggle_wishlist'),

]
