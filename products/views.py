from django.shortcuts import render
from .models import Product


def product_list(request):
    products = Product.objects.filter(is_active=True)
    context={
        'products': products
    }
    return render(request, 'user/products/product_list.html', context)


# Admin View

def admin_product_list(request):
    products = Product.objects.all()
    context={
        'products': products
    }
    return render(request, 'custom_admin/product_list.html', context)
