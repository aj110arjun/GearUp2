# cart/views.py
from django.contrib import messages
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from .models import CartItem
from products.models import ProductVariant
from wishlist.models import Wishlist
from decimal import Decimal
from coupons.models import Coupon
from django.views.decorators.cache import never_cache


@login_required(login_url="login")
@never_cache
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
@never_cache
def cart_view(request):
    error = {}
    items = CartItem.objects.filter(user=request.user).select_related("variant__product")

    subtotal = Decimal("0.00")       # after applying offers
    offer_savings = Decimal("0.00")  # how much saved from offers
    discount = Decimal("0.00")       # coupon discount
    item_qnt_price = Decimal("0.00")
    coupon = None

    for item in items:
        max_limit = min(5, item.variant.stock)

        if item.quantity > max_limit:
            item.quantity = max_limit
            item.save()

        if item.variant.stock == 0:
            item.delete()
            continue
    for item in items:
        item_qnt_price += item.variant.price * item.quantity

        # Original price
        original_price = item.variant.price
        # Discounted price (if offer)
        discounted_price = item.variant.get_discounted_price()

        # Offer savings
        if discounted_price < original_price:
            offer_savings += (original_price - discounted_price) * item.quantity

        # Subtotal after applying product offers
        subtotal += discounted_price * item.quantity

    # 🔹 Coupon logic (applied on top of offers)
    coupon_id = request.session.get("coupon_id")
    if coupon_id:
        try:
            coupon = Coupon.objects.get(code=coupon_id, active=True)
            if coupon.is_valid() and (coupon.min_purchase is None or subtotal >= coupon.min_purchase):
                discount = (subtotal * Decimal(coupon.discount)) / 100
            else:
                error["coupon"] = "Invalid coupon or minimum purchase not met."
                request.session.pop("coupon_id", None)
                coupon = None
        except Coupon.DoesNotExist:
            error["coupon"] = "Coupon does not exist."
            request.session.pop("coupon_id", None)
            coupon = None

    total = subtotal - discount
    if total < 0:
        total = Decimal('0.00')

    return render(
        request,
        "user/cart/cart_view.html",
        {
            "items": items,
            "subtotal": subtotal,         # after offers
            "offer_savings": offer_savings,
            "discount": discount,         # coupon discount
            "total": total,               # final payable
            "coupon": coupon,
            "error": error,
            'item_qnt_price':item_qnt_price,
        },
    )


@login_required(login_url="login")
@never_cache
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
@never_cache
def remove_from_cart(request, item_id):
    cart_item = get_object_or_404(CartItem, id=item_id, user=request.user)
    cart_item.delete()
    return redirect("cart_view")

