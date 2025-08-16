from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from .models import Wishlist
from products.models import Product

@login_required(login_url='login')
def wishlist_view(request):
    items = Wishlist.objects.filter(user=request.user).select_related("product")
    return render(request, "user/wishlist/wishlist_view.html", {"items": items})

@login_required(login_url='login')
def add_to_wishlist(request, pk):
    product = get_object_or_404(Product, pk=pk)
    Wishlist.objects.get_or_create(user=request.user, product=product)
    return redirect("wishlist_view")

@login_required(login_url='login')
def remove_from_wishlist(request, pk):
    item = get_object_or_404(Wishlist, user=request.user, product_id=pk)
    item.delete()
    return redirect("wishlist_view")
