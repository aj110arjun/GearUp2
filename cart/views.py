# cart/views.py
from django.contrib import messages
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from .models import CartItem
from products.models import ProductVariant
from wishlist.models import Wishlist
from decimal import Decimal
from coupons.models import Coupon

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
    subtotal = Decimal("0.00")
    adjusted = False
    has_offer = False  # ✅ flag for offer products

    for item in items:
        max_limit = min(5, item.variant.stock)

        if item.quantity > max_limit:
            item.quantity = max_limit
            item.save()
            adjusted = True

        if item.variant.stock == 0:
            item.delete()
            continue

        # ✅ Check if product has an offer
        discount_percent = item.variant.product.get_best_offer()
        if discount_percent > 0:
            has_offer = True
            price = item.variant.get_discounted_price()
        else:
            price = item.variant.price

        subtotal += item.quantity * price

    if adjusted:
        messages.warning(request, "Some cart items were adjusted due to stock changes.")

    # 🔹 Coupon logic
    coupon = None
    discount = Decimal("0.00")
    coupon_id = request.session.get("coupon_id")

    if has_offer:
        # ✅ If offer exists, remove coupon
        if coupon_id:
            request.session.pop("coupon_id", None)
            messages.info(request, "Coupons cannot be applied when products already have offers.")
    else:
        if coupon_id:
            try:
                coupon = Coupon.objects.get(id=coupon_id, active=True)
                # Check coupon validity
                if coupon.is_valid() and (coupon.min_purchase is None or subtotal >= coupon.min_purchase):
                    discount = (subtotal * Decimal(coupon.discount)) / 100
                else:
                    messages.warning(request, "Invalid coupon or minimum purchase not met.")
                    request.session.pop("coupon_id", None)
                    coupon = None
            except Coupon.DoesNotExist:
                request.session.pop("coupon_id", None)
                coupon = None

    total = subtotal - discount

    return render(
        request,
        "user/cart/cart_view.html",
        {
            "items": items,
            "subtotal": subtotal,
            "discount": discount,
            "total": total,
            "coupon": coupon,
            "has_offer": has_offer,  # ✅ send to template
        },
    )


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

