import razorpay
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
from wallet.models import Wallet, WalletTransaction
from decimal import Decimal
from django.conf import settings
from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse, HttpResponseBadRequest
from coupons.models import Coupon
from django.core.paginator import Paginator
from decimal import Decimal
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect
from django.contrib import messages
from django.utils import timezone
from django.views.decorators.cache import never_cache


from django.contrib.auth.decorators import login_required
from django.views.decorators.cache import never_cache
from django.shortcuts import render, redirect
from django.contrib import messages
from decimal import Decimal
from orders.models import Order, OrderItem, Coupon, Address
from wallet.models import Wallet, WalletTransaction
from transaction.models import Transaction  # Import your Transaction model accordingly

@login_required(login_url="login")
@never_cache
def checkout(request):
    error = {}
    cart_items = CartItem.objects.filter(user=request.user).select_related("variant__product")
    if not cart_items.exists():
        return redirect("cart_view")
    adjusted = False
    subtotal = Decimal("0.00")
    payment_method = request.POST.get("payment_method", "COD")
    wallet, _ = Wallet.objects.get_or_create(user=request.user)
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
        price = Decimal(item.variant.get_discounted_price())
        subtotal += price * item.quantity
    if adjusted:
        messages.warning(request, "Some items were adjusted due to stock limits. Please review your cart again.")
        return redirect("cart_view")
    coupon_id = request.session.get("coupon_id")
    discount = Decimal("0.00")
    coupon = None
    if coupon_id:
        try:
            coupon = Coupon.objects.get(code=coupon_id, active=True)
            if coupon.is_valid() and (coupon.min_purchase is None or subtotal >= coupon.min_purchase):
                discount = (subtotal * Decimal(str(coupon.discount))) / Decimal("100")
                if discount > subtotal:
                    discount = subtotal
            else:
                error['coupon'] = "Invalid coupon or minimum purchase not met."
                coupon = None
                discount = Decimal("0.00")
                request.session.pop("coupon_id", None)
        except Coupon.DoesNotExist:
            error['coupon'] = "Coupon does not exist."
            coupon = None
            discount = Decimal("0.00")
            request.session.pop("coupon_id", None)
    delivery_charge = Decimal("50.00")
    total = subtotal - discount
    if total < 0:
        total = Decimal("0.00")
    grand_total = total + delivery_charge
    if request.method == "POST":
        address_id = request.POST.get("address")
        address = Address.objects.filter(user=request.user, id=address_id).first()
        if not address:
            messages.error(request, "Please select an address before placing your order.")
            addresses = Address.objects.filter(user=request.user)
            return render(request, "user/orders/checkout.html", {
                "error": {"address": "Please select an address before placing your order."},
                "cart_items": cart_items,
                "addresses": addresses,
                "subtotal": subtotal,
                "discount": discount,
                "total": total,
                "coupon": coupon,
                "wallet": wallet,
                "grand_total": grand_total,
                "delivery_charge": delivery_charge,
            })
        if payment_method == "WALLET" and wallet.balance < grand_total:
            error['wallet'] = "Insufficient wallet balance."
        if error:
            addresses = Address.objects.filter(user=request.user)
            return render(request, "user/orders/checkout.html", {
                "error": error,
                "cart_items": cart_items,
                "addresses": addresses,
                "subtotal": subtotal,
                "discount": discount,
                "total": total,
                "coupon": coupon,
                "wallet": wallet,
                "grand_total": grand_total,
                "delivery_charge": delivery_charge,
            })
        order = Order.objects.create(
            user=request.user,
            address=address,
            total_price=grand_total,
            discount=discount,
            coupon=coupon,
            payment_method=payment_method,
            payment_status="Paid" if payment_method == "WALLET" else "Pending",
        )
        for item in cart_items:
            price = Decimal(item.variant.get_discounted_price())
            OrderItem.objects.create(
                order=order,
                variant=item.variant,
                quantity=item.quantity,
                price=price,
            )
            item.variant.stock -= item.quantity
            item.variant.save()
        cart_items.delete()

        # Only create Transaction now for WALLET payments
        if payment_method == "WALLET":
            Transaction.objects.create(
                user=request.user,
                transaction_type="WALLET_DEBIT",
                payment_status="Credit",
                amount=grand_total,
                description=f"Order Payment for Order #{order.order_code} via Wallet",
                order=order,
            )
            wallet.balance -= grand_total
            wallet.save()
            WalletTransaction.objects.create(
                wallet=wallet,
                amount=grand_total,
                transaction_type="DEBIT",
                description=f"Order #{order.order_code} Payment"
            )
            return redirect("order_complete", order_id=order.order_id)

        if payment_method == "COD":
            # You may choose to record a transaction for COD after delivery or here
            return redirect("order_complete", order_id=order.order_id)

        # ONLINE: Don't create a transaction yet; handle in payment_success after confirmation
        return redirect("start_payment", order_id=order.order_id)
    addresses = Address.objects.filter(user=request.user)
    return render(
        request,
        "user/orders/checkout.html",
        {
            "cart_items": cart_items,
            "addresses": addresses,
            "subtotal": subtotal,
            "discount": discount,
            "total": total,
            "coupon": coupon,
            "wallet": wallet,
            "grand_total": grand_total,
            "delivery_charge": delivery_charge,
        },
    )








@login_required(login_url="login")
@never_cache
def order_complete(request, order_id):
    order = get_object_or_404(Order, order_id=order_id, user=request.user)
    items = order.items.select_related("variant__product")
    return render(request, "user/orders/order_complete.html", {"order": order, "items": items})

@login_required(login_url="login")
@never_cache
def order_list(request):
    orders = Order.objects.filter(user=request.user).order_by("-created_at")
    
    paginator = Paginator(orders, 10)  
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    return render(request, "user/orders/orders.html", {"page_obj": page_obj})

@login_required(login_url='login')
@never_cache
def order_detail(request, order_id):
    order = get_object_or_404(Order, order_id=order_id, user=request.user)
    items = order.items.select_related('variant__product')  
    return render(request, 'user/orders/order_detail.html', {'order': order, 'items': items})

@login_required(login_url="login")
@never_cache
def request_return_order_item(request, item_id):
    item = get_object_or_404(OrderItem, item_id=item_id, order__user=request.user)

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
        item.return_approved = None
        item.save()

        messages.success(request, "Return request sent. Admin will review it.")
        return redirect("order_detail", order_id=item.order.order_id)

    return redirect("order_detail", order_id=item.order.order_id)

@staff_member_required(login_url="admin_login")
@never_cache
def admin_order_list(request):
    status_filter = request.GET.get("status", "")
    orders = Order.objects.all().order_by("-created_at")

    if status_filter:
        orders = orders.filter(status=status_filter)

    paginator = Paginator(orders, 10)  
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    return render(
        request,
        "custom_admin/orders/order_list.html",
        {"orders": page_obj} 
    )

@staff_member_required(login_url="admin_login")
@never_cache
def admin_order_detail(request, order_id):
    order = get_object_or_404(Order, order_id=order_id)
    items = OrderItem.objects.filter(order=order).select_related("variant__product")
    return render(request, "custom_admin/orders/order_detail.html", {"order": order, "items": items})

@staff_member_required(login_url="admin_login")
@never_cache
def admin_update_order_item_status(request, item_id):
    order_item = get_object_or_404(OrderItem, item_id=item_id)

    if request.method == "POST":
        new_status = request.POST.get("status")
        if new_status in ["Pending", "Shipped", "Delivered", "Cancelled"]:
            if new_status.lower() in ["pending", "shipped"]:
                order_item.cancellation_requested = False
                order_item.cancellation_reason = ""
                order_item.cancellation_approved = None

            order_item.status = new_status.lower()
            order_item.save()

            if new_status.lower() == "delivered" and order_item.order.payment_method == "COD":
                existing_txn = Transaction.objects.filter(
                    order=order_item.order,
                    transaction_type="COD",
                    description__icontains=f"OrderItem #{order_item.item_id}"
                ).exists()

                if not existing_txn:
                    # Calculate item original price and proportional coupon discount
                    order_items = order_item.order.items.all()
                    order_total_original = sum([
                        Decimal(oi.variant.price) * oi.quantity for oi in order_items
                    ])
                    item_original_price = Decimal(order_item.variant.price) * order_item.quantity
                    coupon_discount_total = getattr(order_item.order, "coupon_discount", Decimal("0.00"))

                    # Proportional coupon discount for this item
                    item_coupon_discount = Decimal("0.00")
                    if order_total_original > 0 and coupon_discount_total > 0:
                        item_coupon_discount = (item_original_price / order_total_original) * coupon_discount_total

                    # Calculate final amount considering coupon discount
                    amount = item_original_price - item_coupon_discount
                    if amount < 0:
                        amount = Decimal('0.00')
                    amount += Decimal('50.00')
                    Transaction.objects.create(
                        user=order_item.order.user,
                        transaction_type="COD",
                        payment_status="Credit",
                        amount=amount,
                        description=f"COD Payment recorded for delivered OrderItem #{order_item.item_id} (Order #{order_item.order.order_code})",
                        order=order_item.order,
                    )

    return redirect("admin_order_detail", order_id=order_item.order.order_id)

# views.py
@login_required(login_url="login")
@never_cache
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

        return redirect("order_detail", order_id=item.order.order_id)

    return redirect("order_detail", order_id=item.order.order_id)
    
@staff_member_required(login_url="admin_login")
@never_cache
def admin_cancellation_requests(request):
    items = OrderItem.objects.filter(cancellation_requested=True, cancellation_approved__isnull=True).select_related("order", "variant__product", "order__user")
    return render(request, "custom_admin/orders/cancellation_request.html", {"items": items})



@staff_member_required(login_url="admin_login")
@never_cache
def admin_approve_reject_cancellation(request, item_id, action):
    item = get_object_or_404(OrderItem, item_id=item_id)

    if action == "approve":
        if item.status != "cancelled":  # prevent double restock and duplicate refunds
            item.status = "cancelled"
            item.cancellation_approved = True

            # Restock product
            item.variant.stock += item.quantity
            item.variant.save()

            # Refund logic for online payments
            if item.order.payment_method in ["ONLINE", "RAZORPAY", "WALLET"]:
                refund_exists = Transaction.objects.filter(
                    order=item.order,
                    transaction_type="WALLET_CREDIT",
                    description__icontains=f"Cancellation refund for OrderItem #{item.item_id}"
                ).exists()
                if not refund_exists:
                    # Calculate total original price for all order items (for proportional discount)
                    order_items = item.order.items.all()
                    order_total_original = sum(Decimal(oi.variant.price) * oi.quantity for oi in order_items)
                    item_original_price = Decimal(item.variant.price) * item.quantity
                    coupon_discount_total = getattr(item.order, "coupon_discount", Decimal("0.00"))
                    # Proportional coupon discount for this item
                    item_coupon_discount = Decimal("0.00")
                    if order_total_original > 0 and coupon_discount_total > 0:
                        item_coupon_discount = (item_original_price / order_total_original) * coupon_discount_total
                    # Calculate final refund amount
                    refund_amount = item_original_price - item_coupon_discount
                    if refund_amount < 0:
                        refund_amount = Decimal('0.00')
                    # Optionally refund shipping fee if your policy requires
                    refund_amount += Decimal("50.00")

                    # Create refund transaction
                    Transaction.objects.create(
                        user=item.order.user,
                        transaction_type="WALLET_CREDIT",
                        payment_status="Debit",
                        amount=refund_amount,
                        description=f"Cancellation refund for OrderItem #{item.item_id} (Order #{item.order.order_code})",
                        order=item.order,
                    )
                    # Credit to user's wallet
                    wallet, _ = Wallet.objects.get_or_create(user=item.order.user)
                    wallet.balance += refund_amount
                    wallet.save()
                    WalletTransaction.objects.create(
                        wallet=wallet,
                        amount=refund_amount,
                        transaction_type="CREDIT",
                        description=f"Refund for cancelled product '{item.variant.product.name}' (x{item.quantity})"
                    )

    elif action == "reject":
        item.cancellation_approved = False

    item.save()
    return redirect("admin_cancellation_requests")



@staff_member_required(login_url="admin_login")
@never_cache
def admin_cancellation_request_view(request, item_id):
    item = get_object_or_404(
        OrderItem,
        item_id=item_id,
        cancellation_requested=True
    )
    order = item.order
    wallet, _ = Wallet.objects.get_or_create(user=order.user)
    
    if request.method == "POST":
        action = request.POST.get("action")
        
        if action == "approve":
            if item.status != "cancelled":  # prevent double cancellation
                item.status = "cancelled"
                item.cancellation_approved = True
                
                # Restock the variant
                item.variant.stock += item.quantity
                item.variant.save()
                
                # Refund to wallet for Razorpay/Online Wallet payments
                if order.payment_method in ["RAZORPAY", "ONLINE", "WALLET"] and order.payment_status == "Paid":
                    refund_amount = item.price * item.quantity
                    refund_amount += Decimal("50.00")  # delivery refund or fixed amount
                    
                    if not getattr(item, "refund_done", False):
                        # ✅ Credit wallet
                        wallet.balance += refund_amount
                        wallet.save()
                        
                        # ✅ Wallet transaction log
                        wallet.transactions.create(
                            transaction_type="CREDIT",
                            amount=refund_amount,
                            description=f"Refund for cancelled product '{item.variant.product.name}' (x{item.quantity})"
                        )

                        # ✅ Global Transaction log
                        Transaction.objects.create(
                            user=order.user,
                            order=order,
                            transaction_type="WALLET_CREDIT",
                            amount=refund_amount,
                            payment_status="Debit",
                            description=f"Refund for cancelled product '{item.variant.product.name}' (x{item.quantity})"
                        )
                        
                        item.refund_done = True
                        
                        messages.success(
                            request,
                            f"Cancellation approved. ₹{refund_amount} has been refunded to {order.user.username}'s wallet."
                        )
                    else:
                        messages.info(request, "Refund already processed for this item.")
                else:
                    messages.info(request, "Cancellation approved without refund (non-online payment).")
        
        elif action == "reject":
            item.cancellation_approved = False
            messages.warning(request, "Cancellation request rejected.")
        
        item.save()
        return redirect("admin_cancellation_requests")
    
    return render(
        request,
        "custom_admin/orders/cancellation_request_view.html",
        {"item": item}
    )


@staff_member_required(login_url="admin_login")
@never_cache
def admin_return_requests(request):
    items = OrderItem.objects.filter(return_requested=True, return_approved__isnull=True) \
                             .select_related("order", "variant__product", "order__user")
    return render(request, "custom_admin/orders/return_request.html", {"items": items})



@staff_member_required(login_url="admin_login")
@never_cache
def admin_approve_reject_return(request, item_id, action):
    errors = {}
    item = get_object_or_404(OrderItem, item_id=item_id)
    
    if not hasattr(item.order.user, "wallet"):
        Wallet.objects.create(user=item.order.user)
    wallet = item.order.user.wallet
    
    # Calculate original total price for all items (before discount)
    order_total_original = sum([
        Decimal(oi.variant.price) * oi.quantity for oi in item.order.items.all()
    ])
    item_original_price = Decimal(item.variant.price) * item.quantity
    coupon_discount = getattr(item.order, "coupon_discount", Decimal("0.00"))
    item_discount = Decimal("0.00")
    if order_total_original > 0 and coupon_discount > 0:
        item_discount = (item_original_price / order_total_original) * coupon_discount
    
    refund_amount = getattr(item, "total_price", None)
    if refund_amount is None:
        refund_amount = item_original_price
    refund_amount = Decimal(refund_amount) - item_discount
    if refund_amount < 0:
        refund_amount = Decimal("0.00")
    
    if action == "approve":
        if item.status == "delivered" and not item.return_approved:
            item.status = "delivered"
            item.return_approved = True
            
            # Restock product
            item.variant.stock += item.quantity
            item.variant.save()
            
            if item.order.payment_method == "COD":
                if not getattr(item, "refund_done", False):
                    wallet.credit(
                        refund_amount,
                        f"Refund for returned product {item.variant.product.name} (x{item.quantity}) including coupon discount"
                    )
                    refund_amount += Decimal('50.00')
                    # Create refund transaction for admin tracking
                    Transaction.objects.create(
                        user=item.order.user,
                        transaction_type="WALLET_CREDIT",
                        payment_status="Debit",
                        amount=refund_amount,
                        description=f"Refund for returned product '{item.variant.product.name}' (Order #{item.order.order_code})",
                        order=item.order,
                    )
                    item.refund_done = True
                    errors['wallet'] = f"Refund of ₹{refund_amount:.2f} credited to {item.order.user.username}'s wallet."
                else:
                    errors['wallet'] = "Refund already processed for this item."
            
            elif item.order.payment_method in ["ONLINE", "RAZORPAY", "WALLET"]:
                refund_amount += Decimal('50.00')
                if not getattr(item, "refund_done", False):
                    wallet.balance += refund_amount
                    wallet.save()
                    wallet.transactions.create(
                        transaction_type="CREDIT",
                        amount=refund_amount,
                        description=f"Refund for returned product '{item.variant.product.name}' (x{item.quantity}) including coupon discount"
                    )
                    # Create refund transaction for admin tracking
                    Transaction.objects.create(
                        user=item.order.user,
                        transaction_type="WALLET_CREDIT",
                        payment_status="Debit",
                        amount=refund_amount,
                        description=f"Refund for returned product '{item.variant.product.name}' (Order #{item.order.order_code})",
                        order=item.order,
                    )
                    WalletTransaction.objects.create(
                        transaction_type="DEBIT",
                        amount=refund_amount,
                        description=f"Refund for returned product '{item.variant.product.name}' (x{item.quantity})"
                        )
                    item.refund_done = True
                    errors['wallet'] = f"Refund of ₹{refund_amount:.2f} credited to {item.order.user.username}'s wallet."
                else:
                    errors['wallet'] = "Refund already processed for this item."
        else:
            errors['return'] = "Return cannot be approved. Either already processed or not delivered."
    
    elif action == "reject":
        item.return_approved = False
        errors['return'] = "Return request rejected."
    
    save_fields = ["status", "return_approved"]
    if hasattr(item, "refund_done"):
        save_fields.append("refund_done")
    item.save(update_fields=save_fields)
    
    return render(request, "custom_admin/wallet/wallet.html", {"item": item, "errors": errors})




@login_required(login_url="login")
@never_cache
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
@never_cache
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
            f"Rs. {item.price}",
            f"Rs. {item.quantity * item.price}",
            f"{item.get_status_display()}",
        ])

    data.append(["", "", "Total:", f"Rs. {order.total_price}"])

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
@never_cache
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
@never_cache
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
@never_cache
def admin_view_return_reason(request, item_id):
    item = get_object_or_404(OrderItem, item_id=item_id)
    return render(request, "custom_admin/orders/view_return_reason.html", {"item": item})

@login_required
@never_cache
def start_payment(request, order_id):
    order = get_object_or_404(Order, order_id=order_id, user=request.user)

    client = razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))

    razorpay_order = client.order.create({
        "amount": int(order.total_price * 100),  # in paise
        "currency": "INR",
        "payment_capture": 1,
    })

    # Save order details
    order.razorpay_order_id = razorpay_order["id"]
    order.save()

    return render(request, "user/orders/payment.html", {
        "order": order,
        "razorpay_key": settings.RAZORPAY_KEY_ID,  # ✅ safe to expose only KEY_ID
        "razorpay_order_id": razorpay_order["id"],
        "amount": order.total_price,
        "currency": "INR",
    })


@login_required(login_url='login')
@never_cache
def order_success(request, order_id):
    order = get_object_or_404(Order, order_id=order_id, user=request.user)
    return render(request, "user/orders/order_success.html", {"order": order})



@csrf_exempt
def payment_success(request, order_id):
    order = get_object_or_404(Order, order_id=order_id)
    if request.method == "POST":
        payment_id = request.POST.get("razorpay_payment_id")
        razorpay_order_id = request.POST.get("razorpay_order_id")
        signature = request.POST.get("razorpay_signature")
        client = razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))
        try:
            client.utility.verify_payment_signature({
                "razorpay_order_id": razorpay_order_id,
                "razorpay_payment_id": payment_id,
                "razorpay_signature": signature
            })
            order.razorpay_payment_id = payment_id
            order.razorpay_signature = signature
            order.payment_status = "Paid"
            order.save()

            # Record transaction ONLY after payment succeeds:
            Transaction.objects.create(
                user=order.user,
                transaction_type='ONLINE_PAYMENT',
                payment_status='Credit',
                amount=order.total_price,
                description=f"Order Payment for Order #{order.order_code} via Razorpay",
                order=order,
            )

            return redirect("order_success", order_id=order.order_id)
        except Exception as e:
            order.payment_status = "Failed"
            order.save()
            return redirect("order_failed", order_id=order.order_id)

        
@login_required(login_url='login')
@never_cache
def payment_failed(request, order_id):
    order = get_object_or_404(Order, order_id=order_id, user=request.user)
    order.payment_status = "Failed"
    order.save()
    return render(request, "user/orders/payment_failed.html", {"order": order})

def retry_payment(request, order_id):
    order = get_object_or_404(Order, order_id=order_id)
    # redirect to the same Razorpay payment page
    return redirect("start_payment", order_id=order.order_id)

