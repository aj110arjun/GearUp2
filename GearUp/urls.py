from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),
    path('register/user/', include('register.urls')),
    path('', include('home.urls')),
    path('account/', include('user_account.urls')),
    path('accounts/', include('allauth.urls')),
]
