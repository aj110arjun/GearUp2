from django.shortcuts import render, get_object_or_404
from decimal import Decimal
from .models import Wallet
from orders.models import OrderItem
from django.contrib.auth.decorators import login_required

@login_required
def approve_return(request, order_item_id):
    """
    Admin view to approve or process a return for an order item.
    Refunds to wallet automatically for COD or RAZORPAY payments.
    """

    errors = {}
    order_item = get_object_or_404(OrderItem, id=order_item_id)
    user = order_item.order.user

    # Ensure the user has a wallet
    wallet, created = Wallet.objects.get_or_create(user=user)

    # Determine refund amount
    refund_amount = getattr(order_item, "total_price", None)
    if refund_amount is None:
        unit_price = getattr(order_item.variant, "price", order_item.price)
        refund_amount = unit_price * order_item.quantity
    refund_amount = Decimal(refund_amount)

    # Check if return is approved and eligible for refund
    if order_item.status.lower() == "return_approved" and order_item.order.payment_method in ["COD", "ONLINE"]:
        
        if getattr(order_item, "refund_done", False):
            errors['wallet'] = "Refund already processed for this item."
        else:
            # Credit refund to wallet
            wallet.balance += refund_amount
            wallet.save()

            # Log transaction
            wallet.transactions.create(
                transaction_type="CREDIT",
                amount=refund_amount,
                description=f"Refund for returned product '{order_item.variant.product.name}' (x{order_item.quantity})"
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
def user_wallet(request):
    wallet = request.user.wallet
    wallet.refresh_from_db()  # ✅ ensures latest balance is fetched
    transactions = wallet.transactions.all().order_by("-created_at")
    return render(request, "user/wallet/wallet.html", {"wallet": wallet, "transactions": transactions})
