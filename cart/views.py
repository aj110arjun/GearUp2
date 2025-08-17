# cart/views.py
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from .models import CartItem
from products.models import ProductVariant
from wishlist.models import Wishlist

@login_required(login_url="login")
def add_to_cart(request, variant_id=None):
    if request.method == "POST":
        variant_id = request.POST.get("variant_id")

    variant = get_object_or_404(ProductVariant, id=variant_id)

    cart_item, created = CartItem.objects.get_or_create(
        user=request.user, variant=variant,
        defaults={"quantity": 1}
    )

    if not created:
        if cart_item.quantity < variant.stock:
            cart_item.quantity += 1
            cart_item.save()

    # remove from wishlist
    Wishlist.objects.filter(user=request.user, product=variant.product).delete()

    return redirect("cart_view")


@login_required(login_url="login")
def cart_view(request):
    items = CartItem.objects.filter(user=request.user).select_related("variant__product")
    total = 0
    adjusted = False  # track if we had to correct anything

    for item in items:
        max_limit = min(5, item.variant.stock)  # whichever is smaller (5 or stock)

        if item.quantity > max_limit:
            item.quantity = max_limit
            item.save()
            adjusted = True

        # If stock is 0, remove the item from cart
        if item.variant.stock == 0:
            item.delete()
        else:
            total += item.quantity * item.variant.price

    # Optional: flash a message if adjustment happened
    if adjusted:
        from django.contrib import messages
        messages.warning(request, "Some cart items were adjusted due to stock changes.")

    return render(request, "user/cart/cart_view.html", {"items": items, "total": total})


@login_required(login_url="login")
def update_cart(request, item_id):
    cart_item = get_object_or_404(CartItem, id=item_id, user=request.user)
    action = request.GET.get("action")

    if action == "increase" and cart_item.quantity < cart_item.variant.stock:
        cart_item.quantity += 1
        cart_item.save()
    elif action == "decrease":
        if cart_item.quantity > 1:
            cart_item.quantity -= 1
            cart_item.save()
        else:
            cart_item.delete()

    return redirect("cart_view")

@login_required(login_url="login")
def remove_from_cart(request, item_id):
    cart_item = get_object_or_404(CartItem, id=item_id, user=request.user)
    cart_item.delete()
    return redirect("cart_view")

