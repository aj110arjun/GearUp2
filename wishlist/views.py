from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from .models import Wishlist
from products.models import Product
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_POST
from django.http import JsonResponse
from django.urls import reverse


@login_required(login_url='login')
@never_cache
def wishlist_view(request):
    items = Wishlist.objects.filter(user=request.user).select_related("product")
    breadcrumbs = [
        ("Home", reverse("home")),
        ("Wishlist", None)
    ]
    context = {
        "items": items,
        "breadcrumbs": breadcrumbs,
    }
    return render(request, "user/wishlist/wishlist_view.html", context)

@login_required(login_url='login')
@require_POST
def toggle_wishlist(request, product_id):
    product = get_object_or_404(Product, id=product_id)
    wishlist_item = Wishlist.objects.filter(user=request.user, product=product).first()

    if wishlist_item:
        wishlist_item.delete()
        status = 'removed'
    else:
        Wishlist.objects.create(user=request.user, product=product)
        status = 'added'

    return JsonResponse({'status': status})

@login_required(login_url='login')
@never_cache
def add_to_wishlist(request, pk):
    product = get_object_or_404(Product, pk=pk)
    Wishlist.objects.get_or_create(user=request.user, product=product)
    return redirect("wishlist_view")

@login_required(login_url='login')
@never_cache
def remove_from_wishlist(request, pk):
    item = get_object_or_404(Wishlist, user=request.user, product_id=pk)
    item.delete()
    return redirect("wishlist_view")
