from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static


urlpatterns = [
    path('', include('home.urls')),
    path('admin/', admin.site.urls),
    path('register/', include('register.urls')),
    path('account/', include('user_account.urls')),
    path('accounts/', include('allauth.urls')),
    path('products/', include('products.urls')),
    path('address/', include('address.urls')),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
