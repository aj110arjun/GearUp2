import razorpay

from django.shortcuts import render, redirect, get_object_or_404
from django.core.paginator import Paginator
from django.http import JsonResponse
from django.conf import settings
from django.urls import reverse
from cart.models import CartItem
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
from django.core.paginator import Paginator
from decimal import Decimal, ROUND_HALF_UP
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
from orders.models import Order, Coupon, Address
from types import SimpleNamespace
from wallet.models import Wallet, WalletTransaction
from transaction.models import Transaction  
from coupons.models import CouponRedemption
from django.db import transaction

# Helper to round to 2 decimal places
def q2(value):
    return round(value, 2)

@login_required(login_url="login")
@never_cache
def checkout(request):
    # Fetch cart items
    cart_items = CartItem.objects.filter(user=request.user).select_related("variant__product")
    if not cart_items.exists():
        messages.info(request, "Your cart is empty.")
        return redirect("cart_view")

    # Tax & Delivery from .env
    tax_rate = Decimal(config("TAX_RATE", 0.18))
    delivery_charge = Decimal(config("DELIVERY_CHARGE", 50))

    # User wallet
    wallet, _ = Wallet.objects.get_or_create(user=request.user)

    # Initialize totals for display
    subtotal = Decimal("0.00")
    total_tax = Decimal("0.00")
    grand_total = Decimal("0.00")
    discount = Decimal("0.00")

    # Compute totals for GET
    for item in cart_items:
        price = Decimal(item.variant.get_discounted_price())
        subtotal += price * item.quantity
    total_tax = q2(subtotal * tax_rate)
    grand_total = q2(subtotal + total_tax + delivery_charge)

    # Apply coupon if any
    coupon_code = request.session.get("coupon_id")
    coupon = None
    if coupon_code:
        try:
            coupon = Coupon.objects.get(code=coupon_code, active=True)
            if hasattr(coupon, "is_valid") and coupon.is_valid():
                discount = q2(min(coupon.discount_value, subtotal))
                grand_total -= discount
            else:
                request.session.pop("coupon_id", None)
                coupon = None
                discount = Decimal("0.00")
        except Coupon.DoesNotExist:
            request.session.pop("coupon_id", None)
            coupon = None
            discount = Decimal("0.00")

    # Handle POST: create orders
    if request.method == "POST":
        payment_method = request.POST.get("payment_method", "COD")
        address_id = request.POST.get("address")
        address = Address.objects.filter(user=request.user, id=address_id).first()
        if not address:
            messages.error(request, "Please select a shipping address.")
            return redirect("checkout")

        created_orders = []

        with transaction.atomic():
            for cart_item in cart_items:
                price = Decimal(cart_item.variant.get_discounted_price())
                item_subtotal = q2(price * cart_item.quantity)
                item_tax = q2(item_subtotal * tax_rate)
                item_total = q2(item_subtotal + item_tax + delivery_charge - discount)

                # Wallet check
                if payment_method == "WALLET" and wallet.balance < item_total:
                    messages.error(request, f"Insufficient wallet balance for {cart_item.variant.product.name}.")
                    return redirect("checkout")

                # Create Order
                order = Order.objects.create(
                    user=request.user,
                    product=cart_item.variant,
                    address=address,
                    quantity=cart_item.quantity,
                    price=price,
                    tax=item_tax,
                    total_price=item_total,
                    discount=discount,
                    coupon=coupon,
                    payment_method=payment_method,
                    payment_status="Paid" if payment_method == "WALLET" else "Pending"
                )
                created_orders.append(order)

                # Reduce stock
                cart_item.variant.stock -= cart_item.quantity
                cart_item.variant.save()

                # Wallet payment
                if payment_method == "WALLET":
                    wallet.balance -= item_total
                    wallet.balance = q2(wallet.balance)
                    wallet.save()
                    WalletTransaction.objects.create(
                        wallet=wallet,
                        amount=item_total,
                        transaction_type="DEBIT",
                        description=f"Order #{order.order_code} Payment"
                    )
                    Transaction.objects.create(
                        user=request.user,
                        transaction_type="WALLET_DEBIT",
                        payment_status="Credit",
                        amount=item_total,
                        description=f"Order Payment for Order #{order.order_code} via Wallet",
                        order=order
                    )

                # Coupon usage
                if coupon:
                    try:
                        coupon.increment_usage(request.user, order)
                    except Exception:
                        pass

        # Clear cart after orders created
        cart_items.delete()

        # Redirect to order complete or payment page
        first_order = created_orders[0]
        if payment_method in ["WALLET", "COD"]:
            return redirect("order_complete", order_id=first_order.order_id)
        else:
            return redirect("start_payment", order_id=first_order.order_id)

    # GET: render checkout page
    addresses = Address.objects.filter(user=request.user)
    context = {
        "cart_items": cart_items,
        "addresses": addresses,
        "wallet": wallet,
        "delivery_charge": delivery_charge,
        "tax_rate": tax_rate,
        "subtotal": subtotal,
        "total_tax": total_tax,
        "grand_total": grand_total,
        "discount": discount,
    }
    return render(request, "user/orders/checkout.html", context)


def order_complete(request, order_id):
    order = get_object_or_404(Order, order_id=order_id, user=request.user)
    subtotal = order.total_price
    discount = order.discount or 0
    total_after_discount = subtotal - discount
    delivery_charge = Decimal(getattr(order, 'delivery_charge', None) or config("DELIVERY_CHARGE"))
    tax_rate = Decimal(config("TAX_RATE"))
    total_tax = q2(total_after_discount * tax_rate)
    grand_total = q2(total_after_discount + total_tax + delivery_charge)

    context = {
        "order": order,
        "subtotal": subtotal,
        "discount": discount,
        "total_tax": total_tax,
        "delivery_charge": delivery_charge,
        "grand_total": grand_total,
    }
    return render(request, "user/orders/order_complete.html", context)

@login_required(login_url='login')
@never_cache
def order_success(request, order_id):
    # All orders created in a single checkout share a purchase_id (you can generate a UUID when user checks out)
    orders = Order.objects.filter(user=request.user, order_id=order_id)

    if not orders.exists():
        return redirect("order_list")

    # Calculate combined totals
    subtotal = sum(order.total_price for order in orders)
    discount = sum(order.discount or 0 for order in orders)
    delivery_charge = Decimal(config("DELIVERY_CHARGE"))
    tax_rate = Decimal(config("TAX_RATE"))
    total_after_discount = subtotal - discount
    total_tax = total_after_discount * tax_rate
    grand_total = total_after_discount + total_tax + delivery_charge

    context = {
        "orders": orders,
        "order_id": order_id,
        "subtotal": subtotal,
        "discount": discount,
        "total_tax": total_tax,
        "delivery_charge": delivery_charge,
        "grand_total": grand_total,
    }

    return render(request, "user/orders/order_success.html", context)



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

    product = order.product
    quantity = order.quantity
    unit_price = order.price
    tax = order.tax
    delivery_charge = Decimal(config("DELIVERY_CHARGE"))
    subtotal = unit_price * quantity
    grand_total = subtotal + tax + delivery_charge - order.discount

    breadcrumbs = [
        ("Home", reverse("home")),
        ("Account", reverse("account_info")),
        ("My Orders", reverse("order_list")),
        (f"#{order.order_code}", None)
    ]

    context = {
        'order': order,
        'product': product,
        'quantity': quantity,
        'unit_price': unit_price,
        'subtotal': subtotal,
        'tax': order.tax,
        'grand_total': grand_total,
        'delivery_charge': delivery_charge,
        'discount': order.discount,
        'breadcrumbs': breadcrumbs,
    }

    return render(request, 'user/orders/order_detail.html', context)



@login_required(login_url="login")
@never_cache
def request_return_order_item(request, item_id):
    # Support both OrderItem (per-item) and Order (single-item) setups
    try:
        from .models import OrderItem as _OrderItem
    except Exception:
        _OrderItem = None

    if _OrderItem:
        item = get_object_or_404(_OrderItem, item_id=item_id, order__user=request.user)
        parent_order = item.order
        status_field = getattr(item, "status", "")
    else:
        # treat item_id as an order_id
        parent_order = get_object_or_404(Order, order_id=item_id, user=request.user)
        # ensure delivered
        status_field = getattr(parent_order, "order_status", "")

    if status_field.lower() != "delivered":
        messages.error(request, "You can only return delivered items.")
        return redirect("order_detail", order_id=getattr(parent_order, "order_id", parent_order.id))

    if request.method == "POST":
        reason = request.POST.get("reason", "").strip()
        if reason:
            if _OrderItem and 'item' in locals():
                item.return_requested = True
                item.return_reason = reason
                item.return_approved = None
                item.save()
            else:
                parent_order.return_requested = True
                parent_order.return_reason = reason
                parent_order.return_approved = None
                parent_order.save(update_fields=["return_requested", "return_reason", "return_approved"])
            messages.success(request, "Return request sent. Admin will review it.")
    return redirect("order_detail", order_id=getattr(parent_order, "order_id", parent_order.id))

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
    # No OrderItem model in this project; adapt the Order into an OrderItem-like object
    adapter = SimpleNamespace(
        variant=getattr(order, "product", None),
        product=getattr(order, "product", None),
        quantity=getattr(order, "quantity", None),
        price=getattr(order, "price", None),
        status=(getattr(order, "order_status", "") or "").lower(),
        order_status=getattr(order, "order_status", None),
        # Provide both order_id and item_id so templates using either won't fail
        order_id=getattr(order, "order_id", None),
        item_id=getattr(order, "order_id", None),
    )
    items = [adapter]
    return render(request, "custom_admin/orders/order_detail.html", {"order": order, "items": items})


@staff_member_required(login_url="admin_login")
@never_cache
def admin_update_order_item_status(request, item_id):
    # The project does not use an OrderItem model. Try updating an Order's status instead.
    # If an OrderItem model is present in globals(), the code could be extended, but here
    # we treat `item_id` as an Order.order_id and update that Order.
    status_order = [s for s, _ in Order.ORDER_STATUS]

    if request.method == "POST":
        new_status = request.POST.get("status")
        if not new_status:
            return redirect("admin_order_list")

        # Normalize incoming status to match model choices (e.g. "Pending", "Shipped")
        normalized = new_status.strip()

        if normalized not in status_order:
            # Try title-casing (in case form used 'pending' etc.)
            normalized = new_status.strip().title()

        if normalized in status_order:
            # Locate order by UUID order_id
            order = get_object_or_404(Order, order_id=item_id)
            try:
                current_index = status_order.index(order.order_status)
            except ValueError:
                current_index = 0
            new_index = status_order.index(normalized)

            if new_index >= current_index:
                # If moving back to earlier states, clear cancellation flags
                if normalized in ["Pending", "Processing"]:
                    order.cancellation_requested = False
                    order.cancellation_reason = ""
                    order.cancellation_approved = None

                # If marking Delivered for a COD order, ensure payment_status is set to Paid
                if normalized == "Delivered" and getattr(order, 'payment_method', '') == 'COD':
                    order.payment_status = 'Paid'

                order.order_status = normalized
                # Build update_fields list to avoid saving unrelated fields
                save_fields = ["order_status"]
                if hasattr(order, 'cancellation_requested'):
                    save_fields += ["cancellation_requested", "cancellation_reason", "cancellation_approved"]
                if getattr(order, 'payment_method', '') == 'COD' and normalized == 'Delivered':
                    save_fields.append('payment_status')

                order.save(update_fields=save_fields) if save_fields else order.save()

                # Handle COD delivered payments similar to previous logic
                if normalized == "Delivered" and order.payment_method == "COD":
                    existing_txn = Transaction.objects.filter(
                        order=order,
                        transaction_type="COD",
                        description__icontains=f"Order #{order.order_code}"
                    ).exists()

                    if not existing_txn:
                        item_price_total = Decimal(order.price) * order.quantity
                        delivery_val = getattr(order, 'delivery_charge', None) or getattr(settings, 'DELIVERY_CHARGE', 0)
                        amount = item_price_total + Decimal(str(delivery_val))

                        Transaction.objects.create(
                            user=order.user,
                            transaction_type="COD",
                            payment_status="Credit",
                            amount=amount,
                            description=f"COD Payment recorded for delivered Order (Order #{order.order_code})",
                            order=order,
                        )

            return redirect("admin_order_detail", order_id=order.order_id)

    # If GET or invalid, redirect to admin order list
    return redirect("admin_order_list")

# views.py
@login_required(login_url="login")
@never_cache
def request_cancel_order_item(request, order_id):
    order = get_object_or_404(Order, order_id=order_id, user=request.user)

    cancellable_statuses = {"Pending", "Processing", "Shipped", "Out For Delivery"}  # choose policy

    if order.order_status not in cancellable_statuses:
        messages.warning(request, f"Cannot cancel order with status {order.order_status}.")
        return redirect("order_detail", order_id=order.order_id)

    if request.method == "POST":
        reason = (request.POST.get("reason") or "").strip()
        if not reason:
            messages.error(request, "Please provide a reason for cancellation.")
            return redirect("order_detail", order_id=order.order_id)

        if order.cancellation_requested:
            messages.info(request, "Cancellation has already been requested for this order.")
            return redirect("order_detail", order_id=order.order_id)

        order.cancellation_requested = True
        order.cancellation_reason = reason
        order.cancellation_approved = None
        order.save(update_fields=["cancellation_requested", "cancellation_reason", "cancellation_approved"])
        messages.success(request, "Cancellation request submitted successfully.")

    return redirect("order_detail", order_id=order.order_id)

@login_required(login_url="login")
@never_cache
def cancel_order_page(request, order_id):
    order = get_object_or_404(Order, order_id=order_id, user=request.user)

    cancellable_statuses = {"Pending", "Processing", "Shipped", "Out For Delivery"}
    if order.order_status not in cancellable_statuses:
        messages.warning(request, f"Cannot cancel this order as its status is '{order.order_status}'.")
        return redirect("order_detail", order_id=order.order_id or order.id)

    if request.method == "POST":
        reason = (request.POST.get("reason") or "").strip()
        if not reason:
            messages.error(request, "Please provide a reason for cancellation.")
            return redirect("order_detail", order_id=order.order_id or order.id)

        if order.cancellation_requested:
            messages.info(request, "A cancellation has already been requested for this order.")
            return redirect("order_detail", order_id=order.order_id or order.id)

        order.cancellation_requested = True
        order.cancellation_reason = reason
        order.cancellation_approved = None
        order.save(update_fields=["cancellation_requested", "cancellation_reason", "cancellation_approved"])
        messages.success(request, "Cancellation request submitted successfully.")
        return redirect("order_detail", order_id=order.order_id or order.id)

    return render(request, "user/orders/cancel_request.html", {"order": order})
    
@staff_member_required(login_url="admin_login")
@never_cache
def admin_cancellation_requests(request):
    orders = Order.objects.filter(
        cancellation_requested=True,
        cancellation_approved__isnull=True
    ).select_related("user", "product", "address")
    
    return render(request, "custom_admin/orders/cancellation_request.html", {"orders": orders})



@staff_member_required(login_url="admin_login")
@never_cache
def admin_approve_reject_cancellation(request, order_id, action):
    order = get_object_or_404(Order, order_id=order_id)

    if action == "approve" and order.order_status != "Cancelled":
        order.order_status = "Cancelled"
        # mark as approved for cancellation
        order.cancellation_approved = True
        order.save(update_fields=["order_status", "cancellation_approved"])

        # --- Compute refund amount ---
        # Prefer using stored total_price if it represents charged amount; fall back to price*quantity.
        base_total = getattr(order, "total_price", None)
        try:
            base_total = Decimal(base_total)
        except Exception:
            base_total = Decimal(order.price) * Decimal(order.quantity)

        tax_amount = getattr(order, "tax", Decimal("0.00")) or Decimal("0.00")
        delivery_charge = Decimal(config("DELIVERY_CHARGE", 0))
        discount_amount = Decimal(getattr(order, "discount", 0) or 0)

        # Expected total based on components (price*qty + tax + delivery - discount)
        expected_total = (Decimal(order.price) * Decimal(order.quantity)) + Decimal(tax_amount) + delivery_charge - discount_amount

        # Use the larger of stored base_total and expected_total to ensure delivery charge is included
        refund_amount = max(base_total, expected_total)

        # Quantize to 2 decimals
        refund_amount = Decimal(refund_amount).quantize(Decimal("0.01"))

        # --- Refund to wallet ONLY if the order was paid ---
        if getattr(order, 'payment_status', None) == 'Paid':
            wallet, _ = Wallet.objects.get_or_create(user=order.user)

            # Prevent duplicate refund: check Transaction for an existing refund for this order
            existing_refund_txn = Transaction.objects.filter(
                user=order.user,
                transaction_type='WALLET_CREDIT',
                amount=refund_amount,
                order=order,
                description__icontains=f"Refund for Order #{order.order_code}"
            ).exists()

            if not existing_refund_txn and refund_amount > Decimal("0.00"):
                # Use Wallet.credit() helper so WalletTransaction is created consistently
                desc = f"Refund for cancelled order (Order #{order.order_code})"
                try:
                    wallet.credit(refund_amount, description=desc)
                except Exception:
                    # Fallback to manual credit if helper fails
                    wallet.balance += refund_amount
                    wallet.save()
                    WalletTransaction.objects.create(
                        wallet=wallet,
                        amount=refund_amount,
                        transaction_type="CREDIT",
                        description=desc
                    )

                Transaction.objects.create(
                    user=order.user,
                    transaction_type="WALLET_CREDIT",
                    payment_status="Debit",
                    amount=refund_amount,
                    description=f"Refund for Order #{order.order_code}",
                    order=order,
                )
                # Mark the order as refunded for UI/reporting
                try:
                    order.payment_status = 'Refund'
                    order.save(update_fields=['payment_status'])
                except Exception:
                    pass
        else:
            # Order not paid yet -- refund should be processed when/if payment arrives or handled manually.
            pass

        # --- Mark coupon as refunded ---
        if order.coupon and not order.coupon_refunded:
            order.coupon_refunded = True
            order.save(update_fields=["coupon_refunded"])
            CouponRedemption.objects.filter(order=order, coupon=order.coupon).update(refunded=True)

    elif action == "reject":
        # Mark the cancellation as rejected
        order.cancellation_approved = False
        order.save(update_fields=["cancellation_approved"])

    return redirect("admin_cancellation_requests")





@staff_member_required(login_url="admin_login")
@never_cache
def admin_cancellation_request_view(request, item_id):
    # Try to import OrderItem; if it doesn't exist, treat item_id as an Order.order_id
    try:
        from .models import OrderItem as _OrderItem
    except Exception:
        _OrderItem = None

    if _OrderItem:
        item = get_object_or_404(_OrderItem, item_id=item_id, cancellation_requested=True)
        if request.method == "POST":
            action = request.POST.get("action")
            return redirect("admin_approve_reject_cancellation", order_id=item.order.order_id, action=action)
        return render(request, "custom_admin/orders/cancellation_request_view.html", {"item": item})
    else:
        # Fallback: fetch Order by order_id and adapt to the template
        order = get_object_or_404(Order, order_id=item_id, cancellation_requested=True)
        adapter = SimpleNamespace(order=order, variant=getattr(order, 'product', None), item_id=getattr(order, 'order_id', None), return_reason=getattr(order, 'cancellation_reason', ''))
        if request.method == "POST":
            action = request.POST.get("action")
            return redirect("admin_approve_reject_cancellation", order_id=order.order_id, action=action)
        return render(request, "custom_admin/orders/cancellation_request_view.html", {"item": adapter})




@staff_member_required(login_url="admin_login")
@never_cache
def admin_return_requests(request):
    # Support both OrderItem-based and Order-based returns
    try:
        from .models import OrderItem as _OrderItem
    except Exception:
        _OrderItem = None

    if _OrderItem:
        items = _OrderItem.objects.filter(return_requested=True, return_approved__isnull=True) \
                             .select_related("order", "variant__product", "order__user")
    else:
        # Adapt Orders into item-like objects for the template
        orders = Order.objects.filter(return_requested=True, return_approved__isnull=True).select_related("user", "product", "address")
        items = []
        for o in orders:
            items.append(SimpleNamespace(order=o, variant=getattr(o, "product", None), quantity=getattr(o, "quantity", 1), return_reason=getattr(o, "return_reason", ""), item_id=getattr(o, "order_id", None)))

    return render(request, "custom_admin/orders/return_request.html", {"items": items})



@staff_member_required(login_url="admin_login")
@never_cache
def admin_approve_reject_return(request, item_id, action):
    # Support both per-item and whole-order return flows
    try:
        from .models import OrderItem as _OrderItem
    except Exception:
        _OrderItem = None

    if _OrderItem:
        item = get_object_or_404(_OrderItem, item_id=item_id)
        order = item.order
        variant = getattr(item, "variant", None)
        qty = getattr(item, "quantity", 1)
        item_tax = getattr(item, "tax", Decimal("0.00"))
        is_item = True
    else:
        # treat item_id as order_id
        order = get_object_or_404(Order, order_id=item_id)
        variant = getattr(order, "product", None)
        qty = getattr(order, "quantity", 1)
        item_tax = getattr(order, "tax", Decimal("0.00"))
        is_item = False

    wallet, _ = Wallet.objects.get_or_create(user=order.user)

    # Calculate refund
    item_price_total = Decimal(getattr(variant, "price", order.price)) * qty
    refund_amount = item_price_total + Decimal(item_tax or 0)

    # Determine if this is the final returned item (for per-item Orders this uses order.items, else assume single-item order)
    if is_item and hasattr(order, 'items'):
        total_items = order.items.count()
        returned_items = order.items.filter(return_approved=True).count()
        if returned_items + 1 == total_items:
            refund_amount += Decimal(config("DELIVERY_CHARGE", 0))
    else:
        # single-order: include delivery charge
        refund_amount += Decimal(config("DELIVERY_CHARGE", 0))

    refund_amount = refund_amount.quantize(Decimal("0.01"))

    if _OrderItem and is_item:
        # per-item approval/rejection
        if action == "approve" and getattr(item, "status", "").lower() == "delivered" and not getattr(item, "return_approved", False):
            item.status = "returned"
            item.return_approved = True
            if hasattr(item, 'variant') and item.variant:
                item.variant.stock += item.quantity
                item.variant.save()

            if not getattr(item, "refund_done", False) and refund_amount > Decimal("0.00"):
                wallet.credit(refund_amount, description=f"Refund for returned product '{item.variant.product.name}' (x{item.quantity})")

                Transaction.objects.create(
                    user=order.user,
                    transaction_type="WALLET_CREDIT",
                    payment_status="Debit",
                    amount=refund_amount,
                    description=f"Refund for returned product '{item.variant.product.name}' (Order #{order.order_code})",
                    order=order,
                )
                # Mark order as refunded (partial refund) for visibility
                try:
                    order.payment_status = 'Refund'
                    order.save(update_fields=['payment_status'])
                except Exception:
                    pass
        elif action == "reject":
            item.return_approved = False

        # save changes for per-item flows
        save_fields = ["status", "return_approved"]
        if hasattr(item, "refund_done"):
            save_fields.append("refund_done")
        item.save(update_fields=save_fields)
    else:
        # single-order approval/rejection
        if action == "approve" and getattr(order, "order_status", "").lower() == "delivered" and not getattr(order, "return_approved", False):
            order.order_status = "Returned"
            order.return_approved = True
            order.save(update_fields=["order_status", "return_approved"])

            if refund_amount > Decimal("0.00"):
                wallet.credit(refund_amount, description=f"Refund for returned order (Order #{order.order_code})")

                Transaction.objects.create(
                    user=order.user,
                    transaction_type="WALLET_CREDIT",
                    payment_status="Debit",
                    amount=refund_amount,
                    description=f"Refund for returned order (Order #{order.order_code})",
                    order=order,
                )
                # Mark the order as refunded
                try:
                    order.payment_status = 'Refund'
                    order.save(update_fields=['payment_status'])
                except Exception:
                    pass
        elif action == "reject":
            order.return_approved = False
            order.save(update_fields=["return_approved"])

    return redirect("admin_return_requests")


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

    # Support both multi-item orders (order.items) and single-item orders (fields on Order)
    if hasattr(order, "items") and hasattr(order.items, "all"):
        items_iterable = order.items.all()
        multi_item = True
    else:
        # Construct a pseudo-item from Order fields
        items_iterable = [SimpleNamespace(
            variant=getattr(order, "product", None),
            quantity=getattr(order, "quantity", 1),
            price=getattr(order, "price", Decimal("0.00")),
            tax=getattr(order, "tax", Decimal("0.00")),
            status=getattr(order, "order_status", "")
        )]
        multi_item = False

    for item in items_iterable:
        item_price = Decimal(getattr(item, "price", 0) or 0)
        item_quantity = int(getattr(item, "quantity", 1) or 1)
        item_tax = Decimal(getattr(item, "tax", 0) or 0)

        item_subtotal = item_price * item_quantity
        subtotal += item_subtotal
        total_tax += item_tax

        product_name = getattr(getattr(item, "variant", None), "product", None)
        if product_name:
            product_name = getattr(product_name, "name", str(product_name))
        else:
            product_name = getattr(order, "product", None)
            if product_name:
                product_name = getattr(product_name, "product", None)
                if product_name:
                    product_name = getattr(product_name, "name", str(product_name))
                else:
                    product_name = str(getattr(order, "product", order))
            else:
                product_name = "Product"

        status_display = getattr(item, "get_status_display", None)
        if callable(status_display):
            status = status_display()
        else:
            status = str(getattr(item, "status", getattr(order, "order_status", "")))

        data.append([
            product_name,
            str(item_quantity),
            f"Rs. {item_price:.2f}",
            f"Rs. {item_tax:.2f}",
            f"Rs. {item_subtotal:.2f}",
            status,
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
    delivery_charge = Decimal(str(getattr(order, 'delivery_charge', None) or config("DELIVERY_CHARGE") or 0))
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
def return_order_item_page(request, item_id):
    # Support both OrderItem-based projects and Order-only projects
    try:
        from .models import OrderItem as _OrderItem
    except Exception:
        _OrderItem = None

    if _OrderItem:
        item = get_object_or_404(_OrderItem, item_id=item_id, order__user=request.user)
        if request.method == "POST":
            reason = request.POST.get("reason")
            item.return_requested = True
            item.return_reason = reason
            item.save()
            messages.success(request, "Return request submitted.")
            return redirect("order_detail", order_id=item.order.order_id)
        return render(request, "user/orders/return_request.html", {"item": item})
    else:
        # treat item_id as an order_id
        order = get_object_or_404(Order, order_id=item_id, user=request.user)
        if request.method == "POST":
            reason = request.POST.get("reason")
            order.return_requested = True
            order.return_reason = reason
            order.return_approved = None
            order.save(update_fields=["return_requested", "return_reason", "return_approved"])
            messages.success(request, "Return request submitted.")
            return redirect("order_detail", order_id=order.order_id)

        # Adapter that the template expects (has .variant and .order)
        adapter = SimpleNamespace(variant=getattr(order, 'product', None), order=order)
        return render(request, "user/orders/return_request.html", {"item": adapter})

@staff_member_required(login_url='admin_login')
@never_cache
def admin_view_return_reason(request, item_id):
    try:
        from .models import OrderItem as _OrderItem
    except Exception:
        _OrderItem = None

    if _OrderItem:
        item = get_object_or_404(_OrderItem, item_id=item_id)
        return render(request, "custom_admin/orders/view_return_reason.html", {"item": item})
    else:
        order = get_object_or_404(Order, order_id=item_id)
        adapter = SimpleNamespace(
            order=order,
            return_reason=getattr(order, 'return_reason', ''),
            item_id=getattr(order, 'order_id', None),
            variant=getattr(order, 'product', None),
            quantity=getattr(order, 'quantity', 1),
        )
        return render(request, "custom_admin/orders/view_return_reason.html", {"item": adapter})

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

@login_required(login_url='admin_login')
@never_cache
def apply_coupon_and_create_order(user, coupon_code, cart_total, **other_order_data):
    coupon = None
    discount_amount = 0
    try:
        coupon = Coupon.objects.get(code=coupon_code)
    except Coupon.DoesNotExist:
        coupon = None

    if coupon and coupon.can_user_use(user):
        discount_amount = (cart_total * coupon.discount) / 100
        grand_total = cart_total - discount_amount
    else:
        grand_total = cart_total

    # create the order atomically
    with transaction.atomic():
        order = Order.objects.create(
            user=user,
            grand_total=grand_total,
            discount=discount_amount,
            coupon=coupon if coupon else None,
            # other fields...
        )

        if coupon:
            # record usage
            CouponUsage.objects.create(user=user, coupon=coupon, order=order)
            coupon.used_by.add(user)
            coupon.total_uses = models.F('total_uses') + 1
            coupon.save(update_fields=['total_uses'])
    return order

