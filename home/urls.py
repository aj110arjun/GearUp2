from django.urls import path
from . import views

urlpatterns = [
   path('',views.home,name='home'),
   path('custom/admin/',views.dashboard,name='dashboard'),
]
