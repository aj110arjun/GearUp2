import json
from django.contrib import messages
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from .models import CartItem
from products.models import ProductVariant
from wishlist.models import Wishlist
from decimal import Decimal
from coupons.models import Coupon
from django.http import JsonResponse
from django.views.decorators.cache import never_cache
from django.template.loader import render_to_string
from django.urls import reverse
from django.views.decorators.http import require_POST


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

@login_required
@require_POST
def toggle_cart(request):
    data = json.loads(request.body)
    variant_id = data.get("variant_id")
    variant = ProductVariant.objects.get(id=variant_id)
    cart_item, created = CartItem.objects.get_or_create(user=request.user, variant=variant)

    if not created:
        cart_item.delete()
        return JsonResponse({"removed": True})
    else:
        return JsonResponse({"added": True})


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
    breadcrumbs = [
        ("Home", reverse("home")),
        ("Cart", None)
    ]

    context = {
        "items": items,
        "subtotal": subtotal,         # after offers
        "offer_savings": offer_savings,
        "discount": discount,         # coupon discount
        "total": total,               # final payable
        "coupon": coupon,
        "error": error,
        'item_qnt_price':item_qnt_price,
        'breadcrumbs': breadcrumbs,
    }

    return render(request,"user/cart/cart_view.html", context)


@login_required(login_url="login")
@never_cache
def update_cart(request, item_id):
    if request.headers.get('x-requested-with') != 'XMLHttpRequest':
        return redirect("cart_view")

    cart_item = get_object_or_404(CartItem, id=item_id, user=request.user)
    action = request.GET.get("action")
    error = {}

    if action == "increase":
        if cart_item.quantity < cart_item.variant.stock:
            cart_item.quantity += 1
            cart_item.save()
        else:
            error['cart'] = "Reached maximum stock limit."
    elif action == "decrease":
        if cart_item.quantity > 1:
            cart_item.quantity -= 1
            cart_item.save()
        else:
            cart_item.delete()
            cart_item = None
    else:
        error['cart'] = "Invalid action."

    if not cart_item:
        quantity = 0
        subtotal_html = "₹0.00"
        max_quantity = 0
    else:
        quantity = cart_item.quantity
        discounted_price = cart_item.variant.get_discounted_price()
        subtotal_amount = discounted_price * quantity

        # Render subtotal HTML snippet
        best_discount = cart_item.variant.product.get_best_offer()
        subtotal_html = render_to_string("partials/cart_item_subtotal.html", {
            "subtotal": subtotal_amount,
            "discount": best_discount,
        })

        max_quantity = min(5, cart_item.variant.stock)

    # Calculate total cart amount considering discounted prices and quantities
    cart_items = CartItem.objects.filter(user=request.user)
    cart_total = Decimal('0.00')
    for item in cart_items:
        price = item.variant.get_discounted_price()
        cart_total += price * item.quantity

    response_data = {
        "success": len(error) == 0,
        "error": error,
        "quantity": quantity,
        "subtotal_html": subtotal_html,
        "cart_total": float(cart_total),
        "max_quantity": max_quantity,
    }

    return JsonResponse(response_data)

@login_required(login_url='login')
def update_variant(request, item_id):
    """Update a cart item's variant (via AJAX or form POST)."""
    cart_item = get_object_or_404(CartItem, id=item_id, user=request.user)

    if request.method == "POST":
        variant_id = request.POST.get("variant_id")
        new_variant = get_object_or_404(ProductVariant, id=variant_id, product=cart_item.variant.product)

        # Replace variant
        cart_item.variant = new_variant
        cart_item.save()

        # If AJAX, return price & stock for live update
        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            data = {
                'price': float(new_variant.get_discounted_price() if hasattr(new_variant, 'get_discounted_price') else new_variant.price),
                'stock': new_variant.stock,
                'variant_text': f"{new_variant.color} / {new_variant.size}"
            }
            return JsonResponse(data)

        return redirect('cart_view')

    return redirect('cart_view')


@login_required(login_url="login")
@never_cache
def remove_from_cart(request, item_id):
    cart_item = get_object_or_404(CartItem, id=item_id, user=request.user)
    cart_item.delete()
    return redirect("cart_view")

