from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.conf.urls import handler404


urlpatterns = [
    path('', include('home.urls')),
    path('admin/', admin.site.urls),
    path('register/', include('register.urls')),
    path('account/', include('user_account.urls')),
    path('accounts/', include('allauth.urls')),
    path('products/', include('products.urls')),
    path('address/', include('address.urls')),
    path('wishlist/', include('wishlist.urls')),
    path('cart/', include('cart.urls')),
    path('orders/', include('orders.urls')),
    path('wallet/', include('wallet.urls')),
    path('coupons/', include('coupons.urls')),
    path('offers/', include('offers.urls')),
    path('transactions/', include('transaction.urls')),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

handler404 = 'register.views.custom_404'
