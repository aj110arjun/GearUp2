# orders/views.py
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from cart.models import CartItem
from .models import Order, OrderItem
from django.contrib.admin.views.decorators import staff_member_required
from address.models import Address
from django.contrib import messages
from django.http import HttpResponse
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib import colors
from io import BytesIO
from wallet.models import Wallet
from decimal import Decimal


# orders/views.py
@login_required(login_url="login")
def checkout(request):
    cart_items = CartItem.objects.filter(user=request.user).select_related("variant__product")
    if not cart_items:
        return redirect("cart_view")

    adjusted = False
    total = 0
    payment_method = request.POST.get("payment_method", "COD")

    # 🔹 Validate stock and limit again before checkout
    for item in cart_items:
        max_limit = min(5, item.variant.stock)

        if item.variant.stock == 0:
            item.delete()
            adjusted = True
            continue

        if item.quantity > max_limit:
            item.quantity = max_limit
            item.save()
            adjusted = True

        total += item.quantity * item.variant.price

    if adjusted:
        messages.warning(request, "Some items were adjusted due to stock limits. Please review your cart again.")
        return redirect("cart_view")

    if request.method == "POST":
        address_id = request.POST.get("address")
        address = Address.objects.filter(user=request.user, id=address_id).first()
        
        if not address:
            messages.error(request, "Please select an address before placing your order.")
            return redirect("checkout")

        order = Order.objects.create(
            user=request.user,
            address=address,
            total_price=total,
            payment_method=payment_method,
        )

        for item in cart_items:
            OrderItem.objects.create(
                order=order,
                variant=item.variant,
                quantity=item.quantity,
                price=item.variant.price,
            )
            # 🔹 Deduct stock safely
            item.variant.stock -= item.quantity
            item.variant.save()

        cart_items.delete()
        return redirect("order_complete", order_id=order.order_id)

    addresses = Address.objects.filter(user=request.user)
    return render(
        request,
        "user/orders/checkout.html",
        {"cart_items": cart_items, "addresses": addresses, "total": total},
    )


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
    item = get_object_or_404(OrderItem, item_id=item_id, order__user=request.user)

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
    errors = {}
    item = get_object_or_404(OrderItem, item_id=item_id)

    # Ensure user has a wallet
    if not hasattr(item.order.user, "wallet"):
        Wallet.objects.create(user=item.order.user)

    wallet = item.order.user.wallet

    if action == "approve":
        if item.status == "delivered" and not item.return_approved:
            item.status = "returned"
            item.return_approved = True

            # Restock product
            item.variant.stock += item.quantity
            item.variant.save()

            # Handle COD refund to wallet
            if item.order.payment_method == "COD":
                refund_amount = getattr(item, "total_price", None)
                if refund_amount is None:
                    unit_price = getattr(item.variant, "price", item.price)
                    refund_amount = unit_price * item.quantity

                if not getattr(item, "refund_done", False):
                    wallet.credit(
                        Decimal(refund_amount),
                        f"Refund for returned product {item.variant.product.name} (x{item.quantity})"
                    )
                    item.refund_done = True
                    errors['wallet'] = f"Refund of ₹{refund_amount} credited to {item.order.user.username}'s wallet."
                else:
                    errors['wallet'] = "Refund already processed for this item."
        else:
            errors['return'] = "Return cannot be approved. Either already processed or not delivered."

    elif action == "reject":
        item.return_approved = False
        errors['return'] = "Return request rejected."

    # Save fields safely
    save_fields = ["status", "return_approved"]
    if hasattr(item, "refund_done"):
        save_fields.append("refund_done")
    item.save(update_fields=save_fields)

    # Render the wallet template for admin to view
    return render(request, "custom_admin/wallet/wallet.html", {"item": item, "errors": errors})


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

@login_required(login_url='login')
def download_invoice(request, order_code):
    order = get_object_or_404(Order, order_code=order_code, user=request.user)

    # Create a file-like buffer
    buffer = BytesIO()

    # Create PDF document
    doc = SimpleDocTemplate(buffer)
    elements = []

    styles = getSampleStyleSheet()
    title_style = styles["Heading1"]
    normal_style = styles["Normal"]

    # Title
    elements.append(Paragraph("Order Invoice", title_style))
    elements.append(Spacer(1, 12))

    # Order Info
    elements.append(Paragraph(f"Order ID: #{order.order_code}", normal_style))
    elements.append(Paragraph(f"Date: {order.created_at.strftime('%d-%m-%Y')}", normal_style))
    elements.append(Paragraph(f"Payment Method: {order.payment_method}", normal_style))
    # elements.append(Paragraph(f"Order Status: {order.payment_method}", normal_style))
    elements.append(Spacer(1, 12))

    elements.append(Paragraph("<b>Shipping Address:</b>", styles["Heading3"]))
    if order.address:
        shipping_address = f"""
        {order.address.full_name}<br/>
        {order.address.address_line_1}<br/>
        {order.address.address_line_2 + '<br/>' if order.address.address_line_2 else ''}
        {order.address.city}, {order.address.state} - {order.address.postal_code}<br/>
        {order.address.country}<br/>
        Phone: {order.address.phone}
     """
        elements.append(Paragraph(shipping_address, styles["Normal"]))
    else:
        elements.append(Paragraph("No shipping address available", styles["Normal"]))
    elements.append(Spacer(1, 12))

    # Order Items Table
    data = [["Product", "Quantity", "Price", "Subtotal", "Status"]]
    for item in order.items.all():
        data.append([
            item.variant.product.name,
            str(item.quantity),
            f"₹{item.price}",
            f"₹{item.quantity * item.price}",
            f"{item.get_status_display()}",
        ])

    data.append(["", "", "Total:", f"₹{order.total_price}"])

    table = Table(data, hAlign="LEFT")
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.grey),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
        ("ALIGN", (1, 1), (-1, -1), "CENTER"),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.black),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
    ]))
    elements.append(table)

    # Build PDF
    doc.build(elements)

    # Get PDF value
    pdf = buffer.getvalue()
    buffer.close()

    # Response as PDF download
    response = HttpResponse(pdf, content_type="application/pdf")
    response["Content-Disposition"] = f'attachment; filename="invoice_#{order.order_code}.pdf"'
    return response

@login_required(login_url="login")
def cancel_order_item_page(request, item_id):
    item = get_object_or_404(OrderItem, item_id=item_id, order__user=request.user)

    if request.method == "POST":
        reason = request.POST.get("reason")
        item.cancellation_requested = True
        item.cancellation_reason = reason
        item.save()
        messages.success(request, "Cancellation request submitted.")
        return redirect("order_detail", order_id=item.order.order_id)

    return render(request, "user/orders/cancel_request.html", {"item": item})


@login_required(login_url="login")
def return_order_item_page(request, item_id):
    item = get_object_or_404(OrderItem, item_id=item_id, order__user=request.user)

    if request.method == "POST":
        reason = request.POST.get("reason")
        item.return_requested = True
        item.return_reason = reason
        item.save()
        messages.success(request, "Return request submitted.")
        return redirect("order_detail", order_id=item.order.order_id)

    return render(request, "user/orders/return_request.html", {"item": item})

@staff_member_required(login_url='admin_login')
def admin_view_return_reason(request, item_id):
    item = get_object_or_404(OrderItem, item_id=item_id)
    return render(request, "custom_admin/orders/view_return_reason.html", {"item": item})










