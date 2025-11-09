# ============================================================================
# UPDATED VIEWS FOR NEW COUPON MODEL (coupons/views.py)
# ============================================================================

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.views.decorators.cache import never_cache
from django.utils.dateparse import parse_datetime
from django.http import JsonResponse
from decimal import Decimal
from products.models import Product
from coupons.models import Coupon, CouponUsage
from decouple import config
from django.utils import timezone



# ----------------- Admin: List Coupons -----------------
@staff_member_required(login_url="admin_login")
@never_cache
def admin_coupon_list(request):
    coupons = Coupon.objects.all().order_by("-valid_from")
    now = timezone.now()
    context = {
        "now": now,
        "coupons": coupons
        }
    return render(request, "custom_admin/coupons/coupon_list.html", context)


# ----------------- Admin: Add Coupon -----------------
@staff_member_required(login_url="admin_login")
@never_cache
def admin_coupon_add(request):
    errors = {}

    if request.method == "POST":
        # Get form data
        code = request.POST.get("code", "").strip().upper()
        discount_percentage = request.POST.get("discount_percentage")
        minimum_order_amount = request.POST.get("minimum_order_amount") or 0
        usage_limit = request.POST.get("usage_limit") or None
        is_active = request.POST.get("is_active") == "on"
        valid_from_str = request.POST.get("valid_from")
        valid_until_str = request.POST.get("valid_until")

        # Validation
        if not code:
            errors["code"] = "Coupon code is required."
        elif Coupon.objects.filter(code=code).exists():
            errors["code"] = "Coupon code must be unique."
        
        if not discount_percentage:
            errors["discount_percentage"] = "Discount percentage is required."
        else:
            try:
                discount_percentage_num = float(discount_percentage)
                if discount_percentage_num <= 0 or discount_percentage_num > 100:
                    errors["discount_percentage"] = "Discount must be between 0 and 100."
            except (TypeError, ValueError):
                errors["discount_percentage"] = "Discount must be a valid number."
        
        if not valid_from_str:
            errors["valid_from"] = "Start date is required."
        
        if not valid_until_str:
            errors["valid_until"] = "End date is required."

        # Date parsing
        valid_from = parse_datetime(valid_from_str) if valid_from_str else None
        valid_until = parse_datetime(valid_until_str) if valid_until_str else None

        if valid_from and valid_until and valid_until < valid_from:
            errors['valid_until'] = "End date cannot be before start date."
        
        # Validate minimum order amount
        try:
            minimum_order_amount = Decimal(str(minimum_order_amount))
            if minimum_order_amount < 0:
                errors["minimum_order_amount"] = "Minimum order amount cannot be negative."
        except:
            errors["minimum_order_amount"] = "Invalid minimum order amount."
        
        
        # Validate usage limit if provided
        if usage_limit:
            try:
                usage_limit = int(usage_limit)
                if usage_limit < 1:
                    errors["usage_limit"] = "Usage limit must be at least 1."
            except:
                errors["usage_limit"] = "Invalid usage limit."

        if errors:
            coupon_data = {
                "code": code,
                "discount_percentage": discount_percentage,
                "minimum_order_amount": minimum_order_amount,
                "usage_limit": usage_limit,
                "is_active": is_active,
                "valid_from": valid_from,
                "valid_until": valid_until,
            }
            context = {
                "action": "Add",
                "coupon": coupon_data,
                "error": errors,
            }
            return render(request, "custom_admin/coupons/coupon_form.html", context)

        # Create coupon
        coupon = Coupon.objects.create(
            code=code,
            discount_percentage=discount_percentage,
            minimum_order_amount=minimum_order_amount,
            usage_limit=usage_limit if usage_limit else None,
            is_active=is_active,
            valid_from=valid_from,
            valid_until=valid_until,
        )

        messages.success(request, f"Coupon '{coupon.code}' created successfully.")
        return redirect("admin_coupon_list")

    context = {
        "action": "Add",
    }
    return render(request, "custom_admin/coupons/coupon_form.html", context)


# ----------------- Admin: Edit Coupon -----------------
@staff_member_required(login_url="admin_login")
@never_cache
def admin_coupon_edit(request, coupon_id):
    coupon = get_object_or_404(Coupon, id=coupon_id)

    if request.method == "POST":
        code = request.POST.get("code", "").strip().upper()
        discount_percentage = request.POST.get("discount_percentage")
        usage_limit = request.POST.get("usage_limit") or None
        is_active = request.POST.get("is_active") == "on"
        valid_from_str = request.POST.get("valid_from")
        valid_until_str = request.POST.get("valid_until")

        # Validation
        errors = {}
        if not code:
            errors["code"] = "Coupon code is required."
        elif Coupon.objects.filter(code=code).exclude(id=coupon_id).exists():
            errors["code"] = "Coupon code must be unique."
        
        if not discount_percentage:
            errors["discount_percentage"] = "Discount percentage is required."
        else:
            try:
                discount_percentage_num = float(discount_percentage)
                if discount_percentage_num <= 0 or discount_percentage_num > 100:
                    errors["discount_percentage"] = "Discount must be between 0 and 100."
            except (TypeError, ValueError):
                errors["discount_percentage"] = "Discount must be a valid number."
        
        if not valid_from_str:
            errors["valid_from"] = "Start date is required."
        
        if not valid_until_str:
            errors["valid_until"] = "End date is required."

        valid_from = parse_datetime(valid_from_str) if valid_from_str else None
        valid_until = parse_datetime(valid_until_str) if valid_until_str else None

        if valid_from and valid_until and valid_until < valid_from:
            errors['valid_until'] = "End date cannot be before start date."

        if errors:
            context = {
                "action": "Edit",
                "coupon": request.POST,
                "error": errors,
                "coupon_id": coupon_id
            }
            return render(request, "custom_admin/coupons/coupon_form.html", context)

        # Save updated coupon
        coupon.code = code
        coupon.discount_percentage = discount_percentage
        coupon.usage_limit = usage_limit if usage_limit else None
        coupon.is_active = is_active
        coupon.valid_from = valid_from
        coupon.valid_until = valid_until
        coupon.save()

        messages.success(request, f"Coupon '{coupon.code}' updated successfully.")
        return redirect("admin_coupon_list")

    return render(request, "custom_admin/coupons/coupon_form.html", {
        "action": "Edit",
        "coupon": coupon
    })


# ----------------- Admin: Delete Coupon -----------------
@staff_member_required(login_url="admin_login")
@never_cache
def admin_coupon_delete(request, coupon_id):
    coupon = get_object_or_404(Coupon, id=coupon_id)
    coupon.delete()
    messages.success(request, f"Coupon {coupon.code} deleted successfully.")
    return redirect("admin_coupon_list")


# ----------------- User: Apply Coupon -----------------
@login_required(login_url="login")
@never_cache
def apply_coupon(request):
    """Apply coupon with comprehensive validation"""
    
    code = request.GET.get("code", "").strip().upper()
    
    if not request.headers.get("x-requested-with") == "XMLHttpRequest":
        return JsonResponse({"success": False, "message": "Invalid request method."})
    
    if not code:
        return JsonResponse({"success": False, "message": "Please enter a coupon code."})
    
    try:
        # Fetch coupon
        coupon = Coupon.objects.get(code=code)
        
        # Calculate cart subtotal
        cart_items = request.user.cart_items.select_related("variant__product")
        if not cart_items.exists():
            return JsonResponse({"success": False, "message": "Your cart is empty."})
        
        subtotal = Decimal('0.00')
        for item in cart_items:
            try:
                price = Decimal(str(item.variant.get_discounted_price()))
                subtotal += price * item.quantity
            except Exception:
                return JsonResponse({
                    "success": False, 
                    "message": "Error calculating cart total."
                })
        
        # Validate coupon with order amount
        is_valid, message = coupon.is_valid(order_amount=subtotal)
        if not is_valid:
            return JsonResponse({"success": False, "message": message})
        
        # Calculate discount
        discount, calc_message = coupon.calculate_discount(subtotal)
        
        if discount == 0:
            return JsonResponse({"success": False, "message": calc_message})
        
        # Calculate final totals
        tax_rate = Decimal(str(config("TAX_RATE", 0.18)))
        delivery_charge = Decimal(str(config("DELIVERY_CHARGE", 0)))
        total_tax = (subtotal * tax_rate).quantize(Decimal("0.01"))
        grand_total = (subtotal + total_tax + delivery_charge - discount)
        
        if grand_total < 0:
            grand_total = Decimal('0.00')
        
        # Store in session
        request.session["coupon_id"] = coupon.code
        request.session.modified = True
        
        return JsonResponse({
            "success": True,
            "code": coupon.code,
            "discount": f"{discount:.2f}",
            "subtotal": f"{subtotal:.2f}",
            "tax": f"{total_tax:.2f}",
            "delivery": f"{delivery_charge:.2f}",
            "new_total": f"{grand_total:.2f}"
        })
        
    except Coupon.DoesNotExist:
        return JsonResponse({"success": False, "message": "Invalid coupon code."})
    except Exception as e:
        return JsonResponse({"success": False, "message": f"Error applying coupon: {str(e)}"})


# ----------------- User: Remove Coupon -----------------
@login_required(login_url="login")
@never_cache
def remove_coupon(request):
    """Remove coupon from session"""
    
    if request.headers.get("x-requested-with") == "XMLHttpRequest":
        if "coupon_id" in request.session:
            del request.session["coupon_id"]
            request.session.modified = True
        
        # Recompute totals
        cart_items = request.user.cart_items.select_related("variant__product")
        subtotal = Decimal('0.00')
        for item in cart_items:
            price = Decimal(str(item.variant.get_discounted_price()))
            subtotal += price * item.quantity

        tax_rate = Decimal(str(config("TAX_RATE", 0.18)))
        delivery_charge = Decimal(str(config("DELIVERY_CHARGE", 0)))
        total_tax = (subtotal * tax_rate).quantize(Decimal("0.01"))
        grand_total = (subtotal + total_tax + delivery_charge)

        return JsonResponse({
            "success": True,
            "subtotal": f"{subtotal:.2f}",
            "tax": f"{total_tax:.2f}",
            "delivery": f"{delivery_charge:.2f}",
            "new_total": f"{grand_total:.2f}",
        })

    if "coupon_id" in request.session:
        del request.session["coupon_id"]
        messages.success(request, "Coupon removed successfully.")
    
    return redirect("checkout")


# ============================================================================
# REFUND COUPON ON RETURN/CANCEL (orders/views.py)
# ============================================================================

@staff_member_required(login_url="admin_login")
@never_cache
def admin_approve_reject_return(request, item_id, action):
    """Return approval with coupon usage refund"""
    
    order = get_object_or_404(Order, order_id=item_id)
    
    if action == "approve" and order.payment_status == "Paid":
        # Calculate refund
        refund_amount = Decimal(order.price) * order.quantity
        refund_amount += order.tax
        refund_amount += Decimal(config("DELIVERY_CHARGE", 0))
        refund_amount = q2(refund_amount)
        
        # Update order
        order.order_status = "Returned"
        order.return_approved = True
        order.save(update_fields=["order_status", "return_approved"])
        
        # Restore stock
        if order.product:
            order.product.stock += order.quantity
            order.product.save()
        
        # Wallet refund
        wallet, _ = Wallet.objects.get_or_create(user=order.user)
        wallet.balance += refund_amount
        wallet.save()
        
        WalletTransaction.objects.create(
            wallet=wallet,
            amount=refund_amount,
            transaction_type="CREDIT",
            description=f"Refund for returned order #{order.order_code}"
        )
        
        # Refund coupon usage
        if order.coupon:
            try:
                usage = CouponUsage.objects.get(
                    coupon=order.coupon,
                    order_id=order.id
                )
                usage.delete()  # Remove usage record
                
                # Decrement usage count
                order.coupon.used_count = max(0, order.coupon.used_count - 1)
                order.coupon.save()
                
                messages.success(
                    request,
                    f"Return approved. Coupon '{order.coupon.code}' is available for reuse."
                )
            except CouponUsage.DoesNotExist:
                messages.success(request, "Return approved.")
        else:
            messages.success(request, "Return approved.")
    
    elif action == "reject":
        order.return_approved = False
        order.save(update_fields=["return_approved"])
        messages.info(request, "Return rejected.")
    
    return redirect("admin_return_requests")