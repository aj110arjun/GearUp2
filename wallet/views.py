import json
import razorpay

from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse
from django.conf import settings
from django.views.decorators.cache import never_cache
from decimal import Decimal
from django.urls import reverse

from .models import Wallet, WalletTransaction
from orders.models import Order


@login_required
@never_cache
def approve_return(request, order_item_id):
    """
    Admin view to approve or process a return for an order item.
    Refunds to wallet automatically for COD or ONLINE (Razorpay) payments.
    Includes coupon discounts, tax, and delivery charges proportionally for the returned item.
    """

    errors = {}
    order_item = get_object_or_404(OrderItem, item_id=order_item_id)
    order = order_item.order
    user = order.user

    wallet, _ = Wallet.objects.get_or_create(user=user)

    # Use the item's total price as the base for refund calculation
    item_price = Decimal(order_item.total_price)

    # Calculate proportional tax for the item
    order_subtotal = Decimal(order.sub_total_price or '0.00')
    order_tax = Decimal(order.tax or '0.00')
    item_tax = (item_price / order_subtotal) * order_tax if order_subtotal > 0 else Decimal('0.00')

    # Calculate proportional delivery charge for the item
    order_delivery_charge = Decimal(order.delivery_charge or '0.00')
    item_delivery_charge = (item_price / order_subtotal) * order_delivery_charge if order_subtotal > 0 else Decimal('0.00')

    # Calculate proportional coupon discount for the item
    order_coupon_discount = Decimal(order.coupon_discount or '0.00')
    item_coupon_discount = (item_price / order_subtotal) * order_coupon_discount if order_subtotal > 0 else Decimal('0.00')

    # Calculate final refund amount
    refund_amount = (item_price + item_tax + item_delivery_charge) - item_coupon_discount
    refund_amount = refund_amount.quantize(Decimal('0.01'))


    if order_item.status.lower() == "return_approved" and order.payment_method in ["COD", "ONLINE"]:
        
        if getattr(order_item, "refund_done", False):
            errors['wallet'] = "Refund already processed for this item."
        else:
            wallet.balance += refund_amount
            wallet.save()

            description = f"Refund for returned product '{order_item.variant.product.name}' (x{order_item.quantity})"
            
            wallet.transactions.create(
                transaction_type="CREDIT",
                amount=refund_amount,
                description=description
            )

            order_item.refund_done = True
            order_item.save(update_fields=["refund_done"])

            # Check if all items in the order are returned to refund the coupon
            all_items_returned = all(item.status == 'Returned' for item in order.items.all())
            if all_items_returned:
                try:
                    redemption = CouponRedemption.objects.get(order=order, user=user)
                    if not redemption.refunded:
                        redemption.refunded = True
                        redemption.save(update_fields=['refunded'])
                except CouponRedemption.DoesNotExist:
                    pass # No coupon was used

            errors['wallet'] = f"Refund of ₹{refund_amount} credited to {user.username}'s wallet."

    else:
        errors['wallet'] = "This order is not eligible for wallet refund."

    context = {
        "order_item": order_item,
        "errors": errors,
        "wallet": wallet
    }

    return render(request, "admin/return_approval.html", context)


    
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
            amount = int(amount) * 100  

            client = razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))

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

    breadcrumbs = [
        ("Home", reverse("home")),
        ("Wallet", None)
    ]

    context = {
        "wallet": wallet, 
        "page_obj": page_obj, 
        "error": error, 
        "razorpay_key": settings.RAZORPAY_KEY_ID,
        "breadcrumbs": breadcrumbs,
        }

    return render(request, "user/wallet/wallet.html", context)
    
@login_required(login_url="login")
@never_cache
def create_order(request):
    if request.method == "POST":
        amount = int(request.POST.get("amount")) * 100  # Convert to paise
        client = razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))
        payment = client.order.create({
            "amount": amount,
            "currency": "INR",
            "payment_capture": "1"
        })
        return JsonResponse(payment)
    return JsonResponse({"error": "Invalid request"}, status=400)

@login_required
def add_money_to_wallet(request):
    error = {}
    wallet, _ = Wallet.objects.get_or_create(user=request.user)

    if request.method == "POST":
        amount_str = request.POST.get("amount")
        try:
            amount = Decimal(amount_str)
            if amount < 10 or amount > 5000:
                error['amount'] = "Enter an amount between 10 and 5000"
            else:
                wallet.balance += amount
                wallet.save()
                # Log the transaction
                WalletTransaction.objects.create(
                    wallet=wallet,
                    transaction_type="CREDIT",
                    amount=amount,
                    description=f"Manual top-up of ₹{amount}."
                )
                return redirect("user_wallet")  # Change to your wallet landing page name
        except:
            error['amount'] = "Invalid amount. Please enter a valid number."

    # Prepare transaction pagination for the GET request or if form input is invalid
    transactions = wallet.transactions.all().order_by("-created_at")
    paginator = Paginator(transactions, 10)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    

    context = {
        "wallet": wallet, 
        "page_obj": page_obj, 
        "error": error,
    }

    return render(request, "user/wallet/wallet.html", context)




def add_money(request):
    if request.method == 'POST':
        amount = Decimal(request.POST.get('amount', '0'))
        if amount > 0:
            request.session['add_wallet_amount'] = str(amount)
            return redirect('wallet_payment')
    breadcrumbs = [
        ("Home", reverse("home")),
        ("Wallet", reverse("user_wallet")),
        ("Add Money", None),
    ]

    context = {
         'error': 'Please enter a valid amount.',
         'breadcrumbs': breadcrumbs
         }

    return render(request, 'user/wallet/add_money.html', context)





def wallet_payment_success(request):
    # Check Razorpay payment signature, status, etc.
    amount = Decimal(request.session.get('add_wallet_amount', '0'))
    if amount > 0:
        wallet, created = Wallet.objects.get_or_create(user=request.user)
        wallet.balance += amount
        wallet.save()
    # Optionally save transaction record
    return redirect('user_wallet')