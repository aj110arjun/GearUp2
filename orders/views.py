# orders/views.py
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from cart.models import CartItem
from .models import Order, OrderItem
from address.models import Address

# orders/views.py
@login_required(login_url="login")
def checkout(request):
    cart_items = CartItem.objects.filter(user=request.user).select_related("variant__product")
    if not cart_items:
        return redirect("cart_view")

    if request.method == "POST":
        address_id = request.POST.get("address")
        address = Address.objects.filter(user=request.user, id=address_id).first()

        total = sum(item.subtotal() for item in cart_items)

        order = Order.objects.create(
            user=request.user,
            address=address,
            total_price=total,
        )

        for item in cart_items:
            OrderItem.objects.create(
                order=order,
                variant=item.variant,
                quantity=item.quantity,
                price=item.variant.price,
            )
            item.variant.stock -= item.quantity
            item.variant.save()

        cart_items.delete()
        return redirect("order_detail", order_id=order.id)

    # 🔹 FIX: make sure we fetch user addresses correctly
    addresses = Address.objects.filter(user=request.user)
    return render(request, "user/orders/checkout.html", {"cart_items": cart_items, "addresses": addresses})


@login_required(login_url="login")
def order_list(request):
    orders = Order.objects.filter(user=request.user).order_by("-created_at")
    return render(request, "user/orders/orders.html", {"orders": orders})

@login_required(login_url="login")
def order_detail(request, order_id):
    order = get_object_or_404(Order, id=order_id, user=request.user)
    return render(request, "user/orders/order_detail.html", {"order": order})

