# orders/views.py
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from cart.models import CartItem
from .models import Order, OrderItem
from django.contrib.admin.views.decorators import staff_member_required
from address.models import Address
from django.contrib import messages


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

@login_required(login_url='login')
def order_detail(request, order_id):
    order = get_object_or_404(Order, id=order_id, user=request.user)
    items = order.items.select_related('variant__product')  # fetch products efficiently
    return render(request, 'user/orders/order_detail.html', {'order': order, 'items': items})

@staff_member_required(login_url="admin_login")
def admin_order_list(request):
    # Optional: filter by status
    status_filter = request.GET.get("status", "")
    orders = Order.objects.all().order_by("-created_at")
    if status_filter:
        orders = orders.filter(status=status_filter)

    return render(request, "custom_admin/orders/order_list.html", {"orders": orders})

@staff_member_required(login_url="admin_login")
def admin_order_detail(request, order_id):
    order = get_object_or_404(Order, id=order_id)
    items = OrderItem.objects.filter(order=order).select_related("variant__product")
    return render(request, "custom_admin/orders/order_detail.html", {"order": order, "items": items})

@staff_member_required(login_url="admin_login")
def admin_update_order_item_status(request, item_id):
    item = get_object_or_404(OrderItem, id=item_id)

    if request.method == "POST":
        new_status = request.POST.get("status")
        if new_status in ["Pending", "Shipped", "Delivered", "Cancelled"]:
            # Reset cancellation if the status is changed to Pending or Shipped
            if new_status.lower() in ["pending", "shipped"]:
                item.cancellation_requested = False
                item.cancellation_reason = ""
                item.cancellation_approved = None
            
            item.status = new_status.lower()
            item.save()
    return redirect("admin_order_detail", order_id=item.order.id)
# views.py
@login_required(login_url="login")
def request_cancel_order_item(request, item_id):
    item = get_object_or_404(OrderItem, id=item_id, order__user=request.user)

    # Only allow if Pending or Shipped
    if item.status not in ["pending", "shipped"]:
        messages.error(request, "You cannot cancel this item.")
        return redirect("order_detail", order_id=item.order.id)

    if request.method == "POST":
        reason = request.POST.get("reason", "").strip()
        if not reason:
            messages.error(request, "You must provide a reason for cancellation.")
            return redirect("order_detail", order_id=item.order.id)

        item.cancellation_requested = True
        item.cancellation_reason = reason
        item.cancellation_approved = None  # pending
        item.save()

        messages.success(request, "Cancellation request sent. Admin will review it.")
        return redirect("order_detail", order_id=item.order.id)

    return redirect("order_detail", order_id=item.order.id)
    
@staff_member_required(login_url="admin_login")
def admin_cancellation_requests(request):
    items = OrderItem.objects.filter(cancellation_requested=True, cancellation_approved__isnull=True).select_related("order", "variant__product", "order__user")
    return render(request, "custom_admin/orders/cancellation_request.html", {"items": items})


@staff_member_required(login_url="admin_login")
def admin_approve_reject_cancellation(request, item_id, action):
    item = get_object_or_404(OrderItem, id=item_id)

    if action == "approve":
        if item.status != "Cancelled":  # prevent double restock
            item.status = "Cancelled"
            item.cancellation_approved = True

            # 🔹 Restock product
            item.variant.stock += item.quantity
            item.variant.save()

    elif action == "reject":
        item.cancellation_approved = False

    item.save()
    return redirect("admin_cancellation_requests")






