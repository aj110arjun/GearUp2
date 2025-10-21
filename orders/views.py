
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
    """Enhanced checkout with proper error handling"""
    
    # Step 1: Validate cart exists
    cart_items = CartItem.objects.filter(user=request.user).select_related("variant__product")
    if not cart_items.exists():
        messages.info(request, "Your cart is empty.")
        return redirect("cart_view")

    # Step 2: Get configuration
    tax_rate = Decimal(config("TAX_RATE", 0.18))
    delivery_charge = Decimal(config("DELIVERY_CHARGE", 50))
    wallet, _ = Wallet.objects.get_or_create(user=request.user)

    # Step 3: Calculate initial totals
    subtotal = Decimal("0.00")
    for item in cart_items:
        try:
            price = Decimal(item.variant.get_discounted_price())
            subtotal += price * item.quantity
        except Exception as e:
            messages.error(request, f"Error calculating price for {item.variant.product.name}")
            return redirect("cart_view")
    
    total_tax = q2(subtotal * tax_rate)
    grand_total = q2(subtotal + total_tax + delivery_charge)

    # Step 4: Validate and apply coupon
    coupon_code = request.session.get("coupon_id")
    coupon = None
    discount = Decimal("0.00")
    
    if coupon_code:
        try:
            coupon = Coupon.objects.get(code=coupon_code, active=True)
            
            # CRITICAL: Validate coupon at checkout time
            if not coupon.is_valid():
                messages.warning(request, f"Coupon '{coupon_code}' has expired or is no longer valid.")
                request.session.pop("coupon_id", None)
                coupon = None
            else:
                discount = q2(min(coupon.discount_value, subtotal))
                grand_total -= discount
                
        except Coupon.DoesNotExist:
            messages.warning(request, "The coupon code in your session is no longer valid.")
            request.session.pop("coupon_id", None)
            coupon = None

    # Step 5: Handle POST (Order Creation)
    if request.method == "POST":
        payment_method = request.POST.get("payment_method", "COD")
        address_id = request.POST.get("address")
        
        # Validate address
        try:
            address = Address.objects.get(user=request.user, id=address_id)
        except Address.DoesNotExist:
            messages.error(request, "Please select a valid shipping address.")
            return redirect("checkout")

        # Validate payment method
        if payment_method not in dict(Order.PAYMENT_METHODS):
            messages.error(request, "Invalid payment method selected.")
            return redirect("checkout")

        # Prepare order data
        cart_list = list(cart_items)
        num_items = len(cart_list)
        created_orders = []
        
        # Calculate per-order discount split
        total_discount = discount
        if total_discount > 0 and num_items > 0:
            total_cents = int((total_discount * 100).quantize(Decimal('1')))
            per_cents = total_cents // num_items
            remainder = total_cents % num_items
        else:
            per_cents = 0
            remainder = 0

        # Step 6: Create orders atomically
        try:
            with transaction.atomic():
                for idx, cart_item in enumerate(cart_list):
                    # Validate stock availability
                    if cart_item.variant.stock < cart_item.quantity:
                        raise ValidationError(
                            f"Insufficient stock for {cart_item.variant.product.name}. "
                            f"Available: {cart_item.variant.stock}, Requested: {cart_item.quantity}"
                        )
                    
                    # Calculate item pricing
                    price = Decimal(cart_item.variant.get_discounted_price())
                    item_subtotal = q2(price * cart_item.quantity)
                    item_tax = q2(item_subtotal * tax_rate)
                    
                    # Calculate this order's discount share
                    this_cents = per_cents + (1 if idx < remainder else 0)
                    this_discount = Decimal(this_cents) / Decimal(100)
                    
                    item_total = q2(item_subtotal + item_tax + delivery_charge - this_discount)
                    
                    # Validate wallet balance if needed
                    if payment_method == "WALLET":
                        if wallet.balance < item_total:
                            raise ValidationError(
                                f"Insufficient wallet balance for {cart_item.variant.product.name}. "
                                f"Required: ₹{item_total}, Available: ₹{wallet.balance}"
                            )
                    
                    # Create order
                    order = Order.objects.create(
                        user=request.user,
                        product=cart_item.variant,
                        address=address,
                        quantity=cart_item.quantity,
                        price=price,
                        tax=item_tax,
                        total_price=item_total,
                        discount=this_discount,
                        coupon=coupon,
                        payment_method=payment_method,
                        payment_status="Paid" if payment_method == "WALLET" else "Pending"
                    )
                    created_orders.append(order)
                    
                    # Reduce stock
                    cart_item.variant.stock -= cart_item.quantity
                    cart_item.variant.save()
                    
                    # Process wallet payment
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
                
                # Record coupon usage ONCE per checkout (not per order)
                if coupon:
                    try:
                        # Use the first order for coupon tracking
                        coupon.increment_usage(request.user, created_orders[0])
                    except Exception as e:
                        # Log but don't fail the order
                        print(f"Coupon increment failed: {e}")
                
                # CRITICAL: Clear coupon from session after successful order
                if "coupon_id" in request.session:
                    del request.session["coupon_id"]
                
                # Clear cart
                cart_items.delete()
                
        except ValidationError as e:
            messages.error(request, str(e))
            return redirect("checkout")
        except Exception as e:
            messages.error(request, f"An error occurred while processing your order: {str(e)}")
            return redirect("checkout")
        
        # Step 7: Store order IDs and redirect
        request.session['recent_purchase_order_ids'] = [str(o.order_id) for o in created_orders]
        request.session.modified = True
        
        first_order = created_orders[0]
        
        if payment_method in ["WALLET", "COD"]:
            return redirect("order_success", order_id=first_order.order_id)
        else:
            request.session['online_payment_order_ids'] = [str(o.order_id) for o in created_orders]
            request.session.modified = True
            return redirect("start_payment", order_id=first_order.order_id)

    # GET: Render checkout page
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
        "coupon": coupon,
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
    # Prefer orders created in the most recent checkout stored in session
    recent_ids = request.session.pop('recent_purchase_order_ids', None)
    if recent_ids:
        orders = Order.objects.filter(order_id__in=recent_ids, user=request.user).order_by('-created_at')
    else:
        # Fallback to showing the current order (by order_id) if present
        try:
            orders = Order.objects.filter(order_id=order_id, user=request.user)
        except Exception:
            orders = Order.objects.filter(user=request.user).order_by('-created_at')

    if not orders.exists():
        return redirect("order_list")

    # Calculate totals across all user orders
    subtotal = sum((order.total_price or Decimal("0.00")) for order in orders)
    discount = sum((order.discount or Decimal("0.00")) for order in orders)

    # Sum per-order stored tax if available, else use TAX_RATE fallback
    try:
        total_tax = sum((order.tax or Decimal("0.00")) for order in orders)
    except Exception:
        tax_rate = Decimal(config("TAX_RATE"))
        total_tax = (subtotal - discount) * tax_rate

    # Sum per-order delivery charges where present, else use configured delivery per order
    delivery_total = Decimal("0.00")
    for order in orders:
        delivery_val = getattr(order, 'delivery_charge', None)
        if delivery_val is None:
            try:
                delivery_val = Decimal(config("DELIVERY_CHARGE"))
            except Exception:
                delivery_val = Decimal("0.00")
        delivery_total += Decimal(delivery_val)

    grand_total = (subtotal - discount) + total_tax + delivery_total

    context = {
        "orders": orders,
        "order_id": order_id,
        "subtotal": subtotal,
        "discount": discount,
        "total_tax": total_tax,
        "delivery_charge": delivery_total,
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
        order.cancellation_approved = True
        order.save(update_fields=["order_status", "cancellation_approved"])

        # --- Compute refund amount (including tax and delivery) ---
        try:
            tax_amount = getattr(order, "tax", Decimal("0.00")) or Decimal("0.00")
            delivery_val = getattr(order, "delivery_charge", None)
            if delivery_val is None:
                try:
                    delivery_val = Decimal(config("DELIVERY_CHARGE", 0))
                except Exception:
                    delivery_val = Decimal("0.00")
            discount_amount = getattr(order, "discount", Decimal("0.00")) or Decimal("0.00")

            base_total = Decimal(order.price) * Decimal(order.quantity)
            refund_amount = (base_total + tax_amount + delivery_val - discount_amount)
            refund_amount = refund_amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        except Exception as e:
            print(f"Error computing refund: {e}")
            refund_amount = Decimal("0.00")

        # --- Refund to wallet ONLY if payment was made ---
        if getattr(order, 'payment_status', None) == 'Paid':
            wallet, _ = Wallet.objects.get_or_create(user=order.user)

            # Prevent duplicate refund transactions
            existing_refund_txn = Transaction.objects.filter(
                user=order.user,
                transaction_type='WALLET_CREDIT',
                amount=refund_amount,
                order=order,
                description__icontains=f"Refund for Order #{order.order_code}"
            ).exists()

            if not existing_refund_txn and refund_amount > Decimal("0.00"):
                refund_desc = f"Refund for cancelled order (Order #{order.order_code})"
                try:
                    wallet.credit(refund_amount, description=refund_desc)
                except Exception:
                    wallet.balance += refund_amount
                    wallet.save()
                    WalletTransaction.objects.create(
                        wallet=wallet,
                        amount=refund_amount,
                        transaction_type="CREDIT",
                        description=refund_desc
                    )

                Transaction.objects.create(
                    user=order.user,
                    transaction_type="WALLET_CREDIT",
                    payment_status="Debit",
                    amount=refund_amount,
                    description=f"Refund for Order #{order.order_code}",
                    order=order,
                )
                try:
                    order.payment_status = 'Refund'
                    order.save(update_fields=['payment_status'])
                except Exception as e:
                    print(f"Error updating payment status: {e}")
        else:
            # Order not paid yet — handle manually later
            pass

        # --- Mark coupon as refunded ---
        if order.coupon and not getattr(order, "coupon_refunded", False):
            order.coupon_refunded = True
            order.save(update_fields=["coupon_refunded"])
            CouponRedemption.objects.filter(order=order, coupon=order.coupon).update(refunded=True)

    elif action == "reject":
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

    # Determine delivery to include: prefer per-order stored delivery_charge, else use config
    delivery_val = getattr(order, 'delivery_charge', None)
    if delivery_val is None:
        try:
            delivery_val = Decimal(config("DELIVERY_CHARGE", 0))
        except Exception:
            delivery_val = Decimal("0.00")

    # Determine if this is the final returned item (for per-item Orders this uses order.items, else assume single-item order)
    if is_item and hasattr(order, 'items'):
        total_items = order.items.count()
        returned_items = order.items.filter(return_approved=True).count()
        if returned_items + 1 == total_items:
            refund_amount += Decimal(delivery_val)
    else:
        # single-order: include delivery charge
        refund_amount += Decimal(delivery_val)

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
    # Support multi-order online payments: if the session contains a list of
    # order ids for online payment, charge the combined amount. Otherwise
    # charge the single order passed in.
    client = razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))

    order_ids = request.session.get('online_payment_order_ids')
    orders = []
    if order_ids:
        # fetch orders ensuring they belong to the user
        orders = list(Order.objects.filter(order_id__in=order_ids, user=request.user))
        if not orders:
            # fallback to single order
            orders = [get_object_or_404(Order, order_id=order_id, user=request.user)]
    else:
        orders = [get_object_or_404(Order, order_id=order_id, user=request.user)]

    # Compute combined amount robustly from order components to ensure tax,
    # delivery and discounts are included even if total_price is missing.
    combined_amount = Decimal("0.00")
    for o in orders:
        try:
            price = Decimal(getattr(o, 'price', 0) or 0)
        except Exception:
            price = Decimal(str(getattr(o, 'price', 0) or 0))
        qty = Decimal(getattr(o, 'quantity', 1) or 1)
        item_subtotal = q2(price * qty)

        # Tax: prefer stored order.tax, else compute using TAX_RATE
        tax_amount = getattr(o, 'tax', None)
        if tax_amount is None:
            try:
                tax_rate = Decimal(config("TAX_RATE", 0.18))
                tax_amount = q2(item_subtotal * tax_rate)
            except Exception:
                tax_amount = Decimal("0.00")
        else:
            try:
                tax_amount = Decimal(tax_amount)
            except Exception:
                tax_amount = Decimal(str(tax_amount))

        # Delivery: prefer stored order.delivery_charge, else use config
        delivery_val = getattr(o, 'delivery_charge', None)
        if delivery_val is None:
            try:
                delivery_val = Decimal(config("DELIVERY_CHARGE", 0))
            except Exception:
                delivery_val = Decimal("0.00")
        else:
            try:
                delivery_val = Decimal(delivery_val)
            except Exception:
                delivery_val = Decimal(str(delivery_val))

        # Discount
        discount_amt = getattr(o, 'discount', None) or Decimal("0.00")
        try:
            discount_amt = Decimal(discount_amt)
        except Exception:
            discount_amt = Decimal(str(discount_amt))

        order_total = q2(item_subtotal + tax_amount + Decimal(delivery_val) - discount_amt)
        combined_amount += order_total

    # Ensure combined_amount is quantized to 2 decimals
    combined_amount = combined_amount.quantize(Decimal('0.01'))

    razorpay_order = client.order.create({
        "amount": int(combined_amount * 100),
        "currency": "INR",
        "payment_capture": 1,
    })

    # Save razorpay_order_id on each order so we can reconcile later
    for o in orders:
        o.razorpay_order_id = razorpay_order["id"]
        o.save(update_fields=["razorpay_order_id"]) 

    # If multiple orders exist, provide `orders` for display; also pick a single
    # `order` for templates that expect a single order (URL reversing, etc.)
    single_order = orders[0] if orders else None
    # Amount in paise for the frontend
    try:
        amount_paise = int((combined_amount * 100).quantize(Decimal('1')))
    except Exception:
        amount_paise = int(Decimal(str(combined_amount or 0)) * 100)

    return render(request, "user/orders/payment.html", {
        "orders": orders,
        "order": single_order,
        "razorpay_key": settings.RAZORPAY_KEY_ID,
        "razorpay_order_id": razorpay_order["id"],
        "amount": combined_amount,
        "amount_paise": amount_paise,
        "currency": "INR",
    })


@csrf_exempt
def payment_success(request, order_id):
    # When paying multiple orders in one Razorpay transaction, the session
    # stores 'online_payment_order_ids'. Prefer that list when marking paid.
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

            order_ids = request.session.get('online_payment_order_ids')
            if order_ids:
                orders = Order.objects.filter(order_id__in=order_ids, user=request.user)
            else:
                orders = Order.objects.filter(order_id=order_id, user=request.user)

            for order in orders:
                order.razorpay_payment_id = payment_id
                order.razorpay_signature = signature
                order.payment_status = "Paid"
                order.save(update_fields=["razorpay_payment_id", "razorpay_signature", "payment_status"])

                Transaction.objects.create(
                    user=order.user,
                    transaction_type='ONLINE_PAYMENT',
                    payment_status='Credit',
                    amount=order.total_price,
                    description=f"Order Payment for Order #{order.order_code} via Razorpay",
                    order=order,
                )

            # Send confirmation for the first order (templates expect a single order)
            first_order = orders.first()
            if first_order:
                subject = "Your Order Has Been Placed Successfully"
                html_message = render_to_string('emails/order_confirmation.html', {'order': first_order, 'user': request.user})
                plain_message = strip_tags(html_message)
                from_email = 'pythondjango110@gmail.com'
                to_email = request.user.email
                send_mail(subject, plain_message, from_email, [to_email], html_message=html_message)

            # Cleanup session
            if 'online_payment_order_ids' in request.session:
                del request.session['online_payment_order_ids']

            return redirect("order_success", order_id=first_order.order_id if first_order else order_id)
        except Exception as e:
            # mark all orders failed if possible
            try:
                order_ids = request.session.get('online_payment_order_ids')
                if order_ids:
                    Order.objects.filter(order_id__in=order_ids, user=request.user).update(payment_status="Failed")
                else:
                    Order.objects.filter(order_id=order_id, user=request.user).update(payment_status="Failed")
            except Exception:
                pass
            return redirect("order_failed", order_id=order_id)

        
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