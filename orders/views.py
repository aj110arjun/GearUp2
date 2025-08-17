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
        return redirect("order_complete", order_id=order.order_id)

    # 🔹 FIX: make sure we fetch user addresses correctly
    addresses = Address.objects.filter(user=request.user)
    return render(request, "user/orders/checkout.html", {"cart_items": cart_items, "addresses": addresses})

@login_required(login_url="login")
def order_complete(request, order_id):
    order = get_object_or_404(Order, order_id=order_id, user=request.user)
    items = order.items.select_related("variant__product")
    return render(request, "user/orders/order_complete.html", {"order": order, "items": items})

@login_required(login_url="login")
def order_list(request):
    orders = Order.objects.filter(user=request.user).order_by("-created_at")
    return render(request, "user/orders/orders.html", {"orders": orders})

@login_required(login_url='login')
def order_detail(request, order_id):
    order = get_object_or_404(Order, order_id=order_id, user=request.user)
    items = order.items.select_related('variant__product')  # fetch products efficiently
    return render(request, 'user/orders/order_detail.html', {'order': order, 'items': items})

@login_required(login_url="login")
def request_return_order_item(request, item_id):
    item = get_object_or_404(OrderItem, item_id=item_id, order__user=request.user)

    # ✅ Only allow return if status is Delivered
    if item.status != "delivered":
        messages.error(request, "You can only return delivered items.")
        return redirect("order_detail", order_id=item.order.order_id)

    if request.method == "POST":
        reason = request.POST.get("reason", "").strip()
        if not reason:
            messages.error(request, "You must provide a reason for return.")
            return redirect("order_detail", order_id=item.order.order_id)

        item.return_requested = True
        item.return_reason = reason
        item.return_approved = None  # pending
        item.save()

        messages.success(request, "Return request sent. Admin will review it.")
        return redirect("order_detail", order_id=item.order.order_id)

    return redirect("order_detail", order_id=item.order.order_id)


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
    order = get_object_or_404(Order, order_id=order_id)
    items = OrderItem.objects.filter(order=order).select_related("variant__product")
    return render(request, "custom_admin/orders/order_detail.html", {"order": order, "items": items})

@staff_member_required(login_url="admin_login")
def admin_update_order_item_status(request, item_id):
    order_item = get_object_or_404(OrderItem, item_id=item_id)

    if request.method == "POST":
        new_status = request.POST.get("status")
        if new_status in ["Pending", "Shipped", "Delivered", "Cancelled"]:
            # Reset cancellation if the status is changed to Pending or Shipped
            if new_status.lower() in ["pending", "shipped"]:
                order_item.cancellation_requested = False
                order_item.cancellation_reason = ""
                order_item.cancellation_approved = None
            
            order_item.status = new_status.lower()
            order_item.save()
    return redirect("admin_order_detail", order_id=order_item.order.order_id)

# views.py
@login_required(login_url="login")
def request_cancel_order_item(request, item_id):
    item = get_object_or_404(OrderItem, id=item_id, order__user=request.user)

    # Only allow if Pending or Shipped
    if item.status not in ["pending", "shipped"]:
        messages.error(request, "You cannot cancel this item.")
        return redirect("order_detail", order_id=item.order.order_id)

    if request.method == "POST":
        reason = request.POST.get("reason", "").strip()
        if not reason:
            messages.error(request, "You must provide a reason for cancellation.")
            return redirect("order_detail", order_id=item.order.order_id)

        item.cancellation_requested = True
        item.cancellation_reason = reason
        item.cancellation_approved = None  # pending
        item.save()

        messages.success(request, "Cancellation request sent. Admin will review it.")
        return redirect("order_detail", order_id=item.order.order_id)

    return redirect("order_detail", order_id=item.order.order_id)
    
@staff_member_required(login_url="admin_login")
def admin_cancellation_requests(request):
    items = OrderItem.objects.filter(cancellation_requested=True, cancellation_approved__isnull=True).select_related("order", "variant__product", "order__user")
    return render(request, "custom_admin/orders/cancellation_request.html", {"items": items})


@staff_member_required(login_url="admin_login")
def admin_approve_reject_cancellation(request, item_id, action):
    item = get_object_or_404(OrderItem, item_id=item_id)

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

@staff_member_required(login_url="admin_login")
def admin_cancellation_request_view(request, item_id):
    item = get_object_or_404(
        OrderItem,
        item_id=item_id,
        cancellation_requested=True
    )

    if request.method == "POST":
        action = request.POST.get("action")
        if action == "approve":
            if item.status != "Cancelled":  # prevent double restock
                item.status = "Cancelled"
                item.cancellation_approved = True
                item.variant.stock += item.quantity
                item.variant.save()
        elif action == "reject":
            item.cancellation_approved = False
        item.save()
        return redirect("admin_cancellation_requests")

    return render(request, "custom_admin/orders/cancellation_request_view.html", {"item": item})

@staff_member_required(login_url="admin_login")
def admin_return_requests(request):
    items = OrderItem.objects.filter(return_requested=True, return_approved__isnull=True) \
                             .select_related("order", "variant__product", "order__user")
    return render(request, "custom_admin/orders/return_request.html", {"items": items})

@staff_member_required(login_url="admin_login")
def admin_approve_reject_return(request, item_id, action):
    item = get_object_or_404(OrderItem, item_id=item_id)

    if action == "approve":
        if item.status == "delivered":  # only approve return if delivered
            item.status = "returned"
            item.return_approved = True

            # 🔹 Restock product
            item.variant.stock += item.quantity
            item.variant.save()

    elif action == "reject":
        item.return_approved = False

    item.save()
    return redirect("admin_return_requests")

@login_required(login_url="login")
def track_order_search(request):
    order = None
    if request.method == "POST":
        order_code = request.POST.get("order_code")
        try:
            order = Order.objects.get(order_code=order_code)
        except Order.DoesNotExist:
            order = None

    return render(request, "user/orders/order_track.html", {"order": order})









