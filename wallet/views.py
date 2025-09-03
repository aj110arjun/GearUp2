from django.shortcuts import render, get_object_or_404, redirect
from decimal import Decimal
from .models import Wallet, WalletTransaction
from orders.models import OrderItem
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse
import json
import razorpay
from django.conf import settings
from django.views.decorators.cache import never_cache


@login_required
@never_cache
def approve_return(request, order_item_id):
    """
    Admin view to approve or process a return for an order item.
    Refunds to wallet automatically for COD or ONLINE (Razorpay) payments.
    Includes coupon discounts proportionally for the returned item.
    """

    errors = {}
    order_item = get_object_or_404(OrderItem, item_id=order_item_id)
    user = order_item.order.user

    # Ensure the user has a wallet
    wallet, _ = Wallet.objects.get_or_create(user=user)

    # Determine refund amount for this item
    refund_amount = getattr(order_item, "total_price", None)
    if refund_amount is None:
        unit_price = getattr(order_item.variant, "price", order_item.price)
        refund_amount = unit_price * order_item.quantity
    refund_amount = Decimal(refund_amount)

    # ================= Handle coupon discount =================
    coupon_discount = getattr(order_item.order, "coupon_discount", Decimal("0.00"))

    # Calculate total of all order items
    order_total = sum([item.total_price for item in order_item.order.items.all()])

    item_discount = Decimal("0.00")
    if order_total > 0 and coupon_discount > 0:
        # Proportion of coupon discount for this item
        item_discount = (refund_amount / order_total) * Decimal(coupon_discount)
        refund_amount += item_discount  # Add coupon portion to refund

    # Check if return is approved and eligible for refund
    if order_item.status.lower() == "return_approved" and order_item.order.payment_method in ["COD", "ONLINE"]:
        
        if getattr(order_item, "refund_done", False):
            errors['wallet'] = "Refund already processed for this item."
        else:
            # Credit refund to wallet
            wallet.balance += refund_amount
            wallet.save()

            # Log transaction with coupon info
            description = f"Refund for returned product '{order_item.variant.product.name}' (x{order_item.quantity})"
            if item_discount > 0:
                description += f" including ₹{item_discount:.2f} coupon discount"

            wallet.transactions.create(
                transaction_type="CREDIT",
                amount=refund_amount,
                description=description
            )

            # Mark order item as refunded
            order_item.refund_done = True
            order_item.save(update_fields=["refund_done"])

            errors['wallet'] = f"Refund of ₹{refund_amount} credited to {user.username}'s wallet."

    else:
        errors['wallet'] = "This order is not eligible for wallet refund."

    # Render template for admin feedback
    return render(request, "admin/return_approval.html", {
        "order_item": order_item,
        "errors": errors,
        "wallet": wallet
    })


    
@login_required(login_url="login")
@never_cache
def user_wallet(request):
    error = {}
    wallet = request.user.wallet
    wallet.refresh_from_db()
    transactions = wallet.transactions.all().order_by("-created_at")

    if request.method == "POST":
        amount = request.POST.get("amount")
        if amount and amount.isdigit() and int(amount) > 0:
            amount = int(amount) * 100  # Razorpay works in paise

            # Razorpay client
            client = razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))

            # Create Razorpay order
            razorpay_order = client.order.create({
                "amount": amount,
                "currency": "INR",
                "payment_capture": "1"
            })

            context = {
                "wallet": wallet,
                "page_obj": Paginator(transactions, 10).get_page(request.GET.get("page")),
                "razorpay_order_id": razorpay_order["id"],
                "razorpay_key": settings.RAZORPAY_KEY_ID,
                "amount": amount,
            }
            return render(request, "user/wallet/wallet_payment.html", context)
        else:
            error['wallet'] = "Please enter a valid amount."

    paginator = Paginator(transactions, 10)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    return render(
        request,
        "user/wallet/wallet.html",
        {"wallet": wallet, "page_obj": page_obj, "error": error, "razorpay_key": settings.RAZORPAY_KEY_ID,}
    )
    
@login_required(login_url="login")
@never_cache
def create_order(request):
    if request.method == "POST":
        amount = int(request.POST.get("amount")) * 100  # in paise

        client = razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))
        payment = client.order.create({
            "amount": amount,
            "currency": "INR",
            "payment_capture": "1"
        })
        return JsonResponse(payment)
    return JsonResponse({"error": "Invalid request"}, status=400)

@csrf_exempt
@login_required(login_url="login")
@never_cache
def wallet_payment_success(request):
    try:
        data = json.loads(request.body)
        razorpay_order_id = data.get("razorpay_order_id")
        razorpay_payment_id = data.get("razorpay_payment_id")
        razorpay_signature = data.get("razorpay_signature")
        client = razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))
        client.utility.verify_payment_signature({
            "razorpay_order_id": razorpay_order_id,
            "razorpay_payment_id": razorpay_payment_id,
            "razorpay_signature": razorpay_signature
        })
        payment = client.payment.fetch(razorpay_payment_id)
        amount = int(payment["amount"]) / 100
        wallet = request.user.wallet
        wallet.balance += amount
        wallet.save()
        # Must always create the transaction for the right wallet, and immediately refresh the object afterward
        WalletTransaction.objects.create(
            wallet=wallet,
            transaction_type="CREDIT",
            amount=amount,
            description=f"Added ₹{amount} via Razorpay (Payment ID: {razorpay_payment_id})"
        )
        wallet.refresh_from_db()
        return JsonResponse({"status": "success"})
    except Exception as e:
        return JsonResponse({"status": "failed", "error": str(e)})