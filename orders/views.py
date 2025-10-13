import razorpay

from django.shortcuts import render, redirect, get_object_or_404
from django.core.paginator import Paginator
from django.http import JsonResponse
from django.conf import settings
from django.urls import reverse
from cart.models import CartItem
from .models import Order, OrderItem
from django.contrib.admin.views.decorators import staff_member_required
from address.models import Address
from django.contrib import messages
from django.http import HttpResponse
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from io import BytesIO
from wallet.models import Wallet, WalletTransaction
from django.conf import settings
from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse, HttpResponseBadRequest
from coupons.models import Coupon
from django.core.paginator import Paginator
from decimal import Decimal
from django.db.models import Sum
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect
from django.contrib import messages
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from django.utils.timezone import now
from django.core.mail import send_mail
from django.contrib.auth.decorators import login_required
from django.views.decorators.cache import never_cache
from django.shortcuts import render, redirect
from django.contrib import messages
from decouple import config
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
    total_tax = Decimal("0.00")
    payment_method = request.POST.get("payment_method", "COD")
    wallet, _ = Wallet.objects.get_or_create(user=request.user)

    tax_rate = Decimal(config("TAX_RATE"))  # 10% tax rate

    # --- Loop through cart items ---
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
        item_subtotal = price * item.quantity
        item_tax = item_subtotal * tax_rate

        subtotal += item_subtotal
        total_tax += item_tax

    if adjusted:
        messages.warning(request, "Some items were adjusted due to stock limits. Please review your cart again.")
        return redirect("cart_view")

    # --- Coupon discount ---
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

    # --- Delivery charge ---
    delivery_charge = Decimal(config("DELIVERY_CHARGE"))

    # --- Totals ---
    total = subtotal - discount
    if total < 0:
        total = Decimal("0.00")

    grand_total = total + delivery_charge + total_tax

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
                "delivery_charge": config("DELIVERY_CHARGE", default="50.00"),
                "tax": total_tax,
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
                "tax": total_tax,
            })

        # --- Create Order ---
        order = Order.objects.create(
            user=request.user,
            address=address,
            total_price=grand_total,
            discount=discount,
            coupon=coupon,
            payment_method=payment_method,
            payment_status="Paid" if payment_method == "WALLET" else "Pending",
        )

        if payment_method != "ONLINE":
            subject = "Your Order Has Been Placed Successfully"
            html_message = render_to_string('emails/order_confirmation.html', {'order': order, 'user': request.user})
            plain_message = strip_tags(html_message)
            from_email = 'pythondjango110@gmail.com'
            to_email = request.user.email
            send_mail(subject, plain_message, from_email, [to_email], html_message=html_message)

        # --- Create Order Items ---
        for item in cart_items:
            price = Decimal(item.variant.get_discounted_price())
            item_subtotal = price * item.quantity
            item_tax = item_subtotal * tax_rate

            OrderItem.objects.create(
                order=order,
                variant=item.variant,
                quantity=item.quantity,
                price=price,
                tax=item_tax,  # ✅ store per-product tax directly
            )

            # Reduce stock
            item.variant.stock -= item.quantity
            item.variant.save()

        # Clear cart
        cart_items.delete()

        # --- Wallet payment handling ---
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
            return redirect("order_complete", order_id=order.order_id)

        return redirect("start_payment", order_id=order.order_id)

    addresses = Address.objects.filter(user=request.user)
    breadcrumbs = [
        ("Home", reverse("home")),
        ("Cart", reverse("cart_view")),
        ("Checkout", None)
    ]
    context = {
        "breadcrumbs": breadcrumbs,
        "cart_items": cart_items,
        "addresses": addresses,
        "subtotal": subtotal,
        "discount": discount,
        "total": total,
        "coupon": coupon,
        "wallet": wallet,
        "grand_total": grand_total,
        "delivery_charge": delivery_charge,
        "tax": total_tax,
        "error": error,
    }

    return render(request, "user/orders/checkout.html", context)



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

    breadcrumbs = [
        ("Home", reverse("home")),
        ("Account", reverse("account_info")),
        ("My Orders", None),
    ]
    context = {
        'page_obj': page_obj,
        'breadcrumbs': breadcrumbs,
    }


    return render(request, "user/orders/orders.html", context)

@login_required(login_url='login')
@never_cache
def order_detail(request, order_id):
    order = get_object_or_404(Order, order_id=order_id, user=request.user)
    grand_total = order.total_price - order.discount
    items = order.items.select_related('variant__product')  

    total_tax = sum(item.tax for item in items)
    subtotal = sum(item.price * item.quantity for item in items)
    grand_total = subtotal + total_tax + Decimal(config("DELIVERY_CHARGE")) - order.discount

    breadcrumbs = [
        ("Home", reverse("home")),
        ("Account", reverse("account_info")),
        ("My Orders", reverse("order_list")),
        (f"#{order.order_code}", None)
    ]

    context = {
        'order': order,
        'items': items,
        'grand_total': grand_total,
        'delivery_charge': config("DELIVERY_CHARGE"),
        'subtotal': subtotal,
        'total_tax': total_tax,
        'discount': order.discount,
        'breadcrumbs': breadcrumbs,

    }
    return render(request, 'user/orders/order_detail.html', context)

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
    errors={}
    order_item = get_object_or_404(OrderItem, item_id=item_id)

    # Define ordered statuses for progression check (lowercase)
    status_order = ["pending", "shipped", "delivered", "cancelled"]

    if request.method == "POST":
        new_status = request.POST.get("status")
        if new_status and new_status.lower() in status_order:
            current_index = status_order.index(order_item.status)
            new_index = status_order.index(new_status.lower())

            # Avoid reverse progression (allow only same or forward status)
            if new_index >= current_index:
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
                        order_items = order_item.order.items.all()
                        order_total_original = sum([
                            Decimal(oi.variant.price) * oi.quantity for oi in order_items
                        ])
                        item_original_price = Decimal(order_item.variant.price) * order_item.quantity
                        coupon_discount_total = getattr(order_item.order, "coupon_discount", Decimal("0.00"))

                        item_coupon_discount = Decimal("0.00")
                        if order_total_original > 0 and coupon_discount_total > 0:
                            item_coupon_discount = (item_original_price / order_total_original) * coupon_discount_total

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
                if new_status.lower() == "delivered":
                    subject = "Your Order Has Been Delivered"
                    context = {
                        'order': order_item.order,
                        'user': order_item.order.user,
                        'now': now(),
                    }
                    html_message = render_to_string('emails/order_delivered.html', context)
                    plain_message = strip_tags(html_message)
                    from_email = 'pythondjango110@gmail.com'
                    to_email = order_item.order.user.email

                    send_mail(subject, plain_message, from_email, [to_email], html_message=html_message)

            else:
                messages.error(request, "Cannot reverse order status progression.")


    return redirect("admin_order_detail", order_id=order_item.order.order_id)

# views.py
@login_required(login_url="login")
@never_cache
def request_cancel_order_item(request, item_id):
    item = get_object_or_404(OrderItem, item_id=item_id, order__user=request.user)

    # Only allow if Pending or Shipped
    if item.status not in ["pending", "shipped"]:
        return redirect("order_detail", order_id=item.order.order_id)

    if request.method == "POST":
        reason = request.POST.get("reason", "").strip()
        if not reason:
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
    order = item.order

    if action == "approve" and item.status != "cancelled":
        item.status = "cancelled"
        item.cancellation_approved = True

        # --- Step 1: Restock the product ---
        item.variant.stock += item.quantity
        item.variant.save()

        # --- Step 2: Refund for online payments ---
        if order.payment_method in ["ONLINE", "RAZORPAY", "WALLET"]:
            refund_exists = Transaction.objects.filter(
                order=order,
                transaction_type="WALLET_CREDIT",
                description__icontains=f"Refund for OrderItem #{item.item_id}"
            ).exists()

            if not refund_exists:
                # Base refund: item price + item tax
                item_price_total = Decimal(item.variant.price) * item.quantity
                item_tax = getattr(item, "tax", Decimal("0.00"))
                refund_amount = (item_price_total + item_tax).quantize(Decimal("0.01"))

                remaining_items = order.items.exclude(status="cancelled").exclude(item_id=item.item_id)

                if not remaining_items.exists():
                    # 🧾 Last item cancelled → include delivery charge in refund
                    delivery_charge = Decimal(int(config("DELIVERY_CHARGE")))
                    refund_amount += delivery_charge
                    refund_amount = refund_amount.quantize(Decimal("0.01"))

                # --- Step 3: Create refund transaction ---
                Transaction.objects.create(
                    user=order.user,
                    transaction_type="WALLET_CREDIT",
                    payment_status="Debit",
                    amount=refund_amount,
                    description=f"Refund for OrderItem #{item.item_id} (Order #{order.order_code})",
                    order=order,
                )

                # --- Step 4: Credit to user's wallet ---
                wallet, _ = Wallet.objects.get_or_create(user=order.user)
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
    item = get_object_or_404(OrderItem, item_id=item_id, cancellation_requested=True)

    if request.method == "POST":
        action = request.POST.get("action")
        # Redirect to the approval function
        return redirect("admin_approve_reject_cancellation", item_id=item.item_id, action=action)

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
    order = item.order

    # Ensure wallet exists
    if not hasattr(order.user, "wallet"):
        Wallet.objects.create(user=order.user)
    wallet = order.user.wallet

    # --- Step 1: Calculate base order details ---
    order_total_original = sum([
        Decimal(oi.variant.price) * oi.quantity for oi in order.items.all()
    ])
    item_original_price = Decimal(item.variant.price) * item.quantity

    # --- Step 2: Proportional coupon discount for this item ---
    coupon_discount = getattr(order, "coupon_discount", Decimal("0.00"))
    item_discount = Decimal("0.00")
    if order_total_original > 0 and coupon_discount > 0:
        item_discount = (item_original_price / order_total_original) * coupon_discount

    # --- Step 3: Calculate refund amount (price * qty - discount) ---
    refund_amount = item_original_price - item_discount

    # --- Step 4: Add tax if present ---
    if hasattr(item, "tax"):
        refund_amount += Decimal(item.tax)

    # --- Step 5: Check if this is the final (last) returned item ---
    total_items = order.items.count()
    returned_items = order.items.filter(return_approved=True).count()
    delivery_charge = int(config("DELIVERY_CHARGE"))

    # If this item is the last to be returned, include delivery charge
    if returned_items + 1 == total_items:
        refund_amount += delivery_charge

    # --- Step 6: Round to 2 decimal places ---
    refund_amount = refund_amount.quantize(Decimal("0.01"))

    # --- Step 7: Handle admin action ---
    if action == "approve":
        if item.status == "delivered" and not item.return_approved:
            item.status = "returned"  # keeps status consistent
            item.return_approved = True

            # Restock returned items
            item.variant.stock += item.quantity
            item.variant.save()

            if not getattr(item, "refund_done", False):
                # Credit refund to wallet
                wallet.credit(
                    refund_amount,
                    f"Refund for returned product '{item.variant.product.name}' (x{item.quantity})"
                )

                # Record transaction for tracking
                Transaction.objects.create(
                    user=order.user,
                    transaction_type="WALLET_CREDIT",
                    payment_status="Debit",
                    amount=refund_amount,
                    description=f"Refund for returned product '{item.variant.product.name}' (Order #{order.order_code})",
                    order=order,
                )

                item.refund_done = True
                errors["wallet"] = f"Refund of Rs. {refund_amount:.2f} credited to {order.user.username}'s wallet."
            else:
                errors["wallet"] = "Refund already processed for this item."
        else:
            errors["return"] = "Return cannot be approved. Either already processed or not delivered."

    elif action == "reject":
        item.return_approved = False
        errors["return"] = "Return request rejected."

    # --- Step 8: Save changes ---
    save_fields = ["status", "return_approved"]
    if hasattr(item, "refund_done"):
        save_fields.append("refund_done")
    item.save(update_fields=save_fields)

    return render(request, "custom_admin/orders/return_request.html", {"item": item, "errors": errors})


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

    breadcrumbs = [
        ("Home", reverse("home")),
        ("Account", reverse("account_info")),
        ("Track Order", None),
    ]

    context = {
        "order": order,
        "breadcrumbs": breadcrumbs,
    }

    return render(request, "user/orders/order_track.html", context)

@login_required(login_url='login')
@never_cache
def download_invoice(request, order_code):
    order = get_object_or_404(Order, order_code=order_code, user=request.user)

    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, topMargin=40, leftMargin=40, rightMargin=40, bottomMargin=40)
    elements = []

    styles = getSampleStyleSheet()
    title_style = styles["Heading1"]
    normal_style = styles["Normal"]

    # --- Title ---
    elements.append(Paragraph("<b>Order Invoice</b>", title_style))
    elements.append(Spacer(1, 12))

    # --- Order Info ---
    elements.append(Paragraph(f"Order ID: #{order.order_code}", normal_style))
    elements.append(Paragraph(f"Date: {order.created_at.strftime('%d-%m-%Y')}", normal_style))
    elements.append(Paragraph(f"Payment Method: {order.payment_method}", normal_style))
    elements.append(Spacer(1, 12))

    # --- Shipping Address ---
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
        elements.append(Paragraph(shipping_address, normal_style))
    else:
        elements.append(Paragraph("No shipping address available", normal_style))
    elements.append(Spacer(1, 15))

    # --- Order Items Table ---
    data = [["Product", "Qty", "Unit Price", "Tax", "Subtotal", "Status"]]

    subtotal = Decimal("0.00")
    total_tax = Decimal("0.00")

    for item in order.items.all():
        item_subtotal = item.price * item.quantity
        subtotal += item_subtotal
        total_tax += item.tax or Decimal("0.00")

        data.append([
            item.variant.product.name,
            str(item.quantity),
            f"Rs. {item.price:.2f}",
            f"Rs. {item.tax:.2f}",
            f"Rs. {item_subtotal:.2f}",
            item.get_status_display(),
        ])

    table = Table(data, hAlign="LEFT", colWidths=[140, 40, 70, 70, 80, 80])
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#4a4a4a")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.grey),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("BOTTOMPADDING", (0, 0), (-1, 0), 6),
        ("TOPPADDING", (0, 0), (-1, 0), 6),
    ]))
    elements.append(table)
    elements.append(Spacer(1, 15))

    # --- Summary Section ---
    delivery_charge = Decimal(str(config("DELIVERY_CHARGE") or 0))
    discount = Decimal(str(order.discount or 0))
    grand_total = subtotal + total_tax + delivery_charge - discount

    summary_data = [
    ["Subtotal:", f"Rs. {subtotal:.2f}"],
    ["Tax:", f"Rs. {total_tax:.2f}"],
    ["Delivery Charge:", f"Rs. {delivery_charge:.2f}"],
]

    # Add discount row only if discount exists and is greater than 0
    if discount > 0:
        summary_data.append(["Discount:", f"- Rs. {discount:.2f}"])

    summary_data.append(["Grand Total:", f"Rs. {grand_total:.2f}"])

    summary_table = Table(summary_data, hAlign="RIGHT", colWidths=[150, 100])
    summary_table.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, -2), "Helvetica"),
        ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
        ("ALIGN", (0, 0), (-1, -1), "RIGHT"),
        ("FONTSIZE", (0, 0), (-1, -1), 10),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    elements.append(summary_table)

    elements.append(Spacer(1, 15))
    elements.append(Paragraph("<i>Thank you for shopping with GearUp!</i>", normal_style))

    # --- Build PDF ---
    doc.build(elements)
    pdf = buffer.getvalue()
    buffer.close()

    response = HttpResponse(pdf, content_type="application/pdf")
    response["Content-Disposition"] = f'attachment; filename="invoice_{order.order_code}.pdf"'
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
            subject = "Your Order Has Been Placed Successfully"
            html_message = render_to_string('emails/order_confirmation.html', {'order': order, 'user': request.user})
            plain_message = strip_tags(html_message)
            from_email = 'pythondjango110@gmail.com'
            to_email = request.user.email

            send_mail(subject, plain_message, from_email, [to_email], html_message=html_message)

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

