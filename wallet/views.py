from django.shortcuts import render, get_object_or_404
from decimal import Decimal
from .models import Wallet
from orders.models import OrderItem
from django.contrib.auth.decorators import login_required


def approve_return(request, order_item_id):
    errors = {}
    order_item = get_object_or_404(OrderItem, id=order_item_id)

    # Ensure user has a wallet
    if not hasattr(order_item.order.user, "wallet"):
        Wallet.objects.create(user=order_item.order.user)

    wallet = order_item.order.user.wallet
    refund_amount = getattr(order_item, "total_price", None)
    
    if refund_amount is None:
        # Use variant price if available, otherwise fall back to order_item.price
        unit_price = getattr(order_item.variant, "price", order_item.price)
        refund_amount = unit_price * order_item.quantity

    # Check COD and Return Approved
    if order_item.order.payment_method == "COD" and order_item.status == "RETURN_APPROVED":

        # Prevent double refund
        if not getattr(order_item, "refund_done", False):
            wallet.credit(
                Decimal(refund_amount),
                description=f"Refund for returned product {order_item.variant.product.name}",
                product_quantity=order_item.quantity
            )
            order_item.refund_done = True
            order_item.save(update_fields=["refund_done"])
            errors['wallet'] = f"Refund of ₹{refund_amount} credited to {order_item.order.user.username}'s wallet."
        else:
            errors['wallet'] = "Refund already processed for this item."
    else:
        errors['wallet'] = "This order is not eligible for wallet refund."

    # Render the template and pass errors
    return render(request, "admin/return_approval.html", {
        "order_item": order_item,
        "errors": errors
    })

    
@login_required(login_url="login")
def user_wallet(request):
    wallet = request.user.wallet  # wallet should exist via signal
    transactions = wallet.transactions.all().order_by("-created_at")
    return render(request, "user/wallet/wallet.html", {"wallet": wallet, "transactions": transactions})
