from django.shortcuts import redirect, get_object_or_404, render
from django.utils import timezone
from django.contrib import messages
from .models import Coupon
from django.contrib.admin.views.decorators import staff_member_required
from .forms import CouponApplyForm
from decimal import Decimal
from .models import Coupon
from cart.models import CartItem

def apply_coupon(request):
    if request.method == "POST":
        code = request.POST.get("code", "").strip()
        if not code:
            messages.error(request, "Please enter a coupon code.")
            return redirect("cart_view")

        coupon = get_object_or_404(Coupon, code__iexact=code, active=True)

        # Calculate current cart subtotal
        cart_items = CartItem.objects.filter(user=request.user)
        subtotal = sum(item.quantity * item.variant.price for item in cart_items)

        # Check minimum purchase requirement
        if coupon.min_purchase and subtotal < coupon.min_purchase:
            messages.error(request, f'Coupon requires minimum purchase of ₹{coupon.min_purchase}.')
            return redirect("cart_view")

        # Calculate discount (percentage only)
        discount = subtotal * Decimal(coupon.discount / 100)

        # Save coupon in session
        request.session['coupon_id'] = coupon.id
        request.session['discount'] = float(discount)  # for JSON serialization
        messages.success(request, f'Coupon "{coupon.code}" applied successfully!')

    return redirect("cart_view")

def remove_coupon(request):
    request.session.pop("coupon_id", None)
    return redirect("cart_view")

@staff_member_required(login_url='admin:login')
def admin_coupon_list(request):
    coupons = Coupon.objects.all().order_by('-valid_from')  # Order by latest
    context = {
        'coupons': coupons,
    }
    return render(request, 'custom_admin/coupons/coupon_list.html', context)

from decimal import Decimal
from django.utils.dateparse import parse_datetime
from django.contrib import messages
from django.shortcuts import render, redirect
from django.contrib.admin.views.decorators import staff_member_required
from .models import Coupon

@staff_member_required(login_url='admin_login')
def admin_coupon_add(request):
    error={}
    if request.method == "POST":
        code = request.POST.get("code", "").strip()
        discount = request.POST.get("discount")
        min_purchase = request.POST.get("min_purchase") or None
        active = request.POST.get("active") == "on"

        # Parse the datetime fields
        valid_from_str = request.POST.get("valid_from")
        valid_to_str = request.POST.get("valid_to")
        valid_from = parse_datetime(valid_from_str) if valid_from_str else None
        valid_to = parse_datetime(valid_to_str) if valid_to_str else None

        if not code:
            error["code"] = "Coupon code is required"
        else:
            if Coupon.objects.filter(code=code).exists():
                error["code"] = "Coupon code is already exist"
            
        if not discount:
            error["discount"] = "Discount is required"
        else:   
            if int(discount) < 10 or int(discount) > 90:
                error["discount"] = "Discount must be in between 10 and 90"
                
        if not min_purchase:
            error["min_purchase"] = "Minimum purchase amount is required"
        else:
            if int(min_purchase) < 100:
                error["min_purchase"] = "Minimum purchase amount must be greater than 100"
            
        if not valid_from:
            error["valid_from"] = "Valid from is required"
            
        if not valid_to:
            error["valid_to"] = "Valid to is required"

        if not error:
            Coupon.objects.create(
                code=code,
                discount=Decimal(discount),
                min_purchase=Decimal(min_purchase) if min_purchase else None,
                active=active,
                valid_from=valid_from,
                valid_to=valid_to
            )
            return redirect("admin_coupon_list")

    return render(request, "custom_admin/coupons/coupon_form.html", {"action": "Add", "error": error})

@staff_member_required(login_url='admin_login')
def admin_coupon_edit(request, id):
    error={}
    coupon = get_object_or_404(Coupon, id=id)

    if request.method == "POST":
        code = request.POST.get("code").strip()
        discount = request.POST.get("discount")
        min_purchase = request.POST.get("min_purchase") or None
        active = request.POST.get("active") == "on"

        if not code:
            error["code"] = "Coupon code is required"
        else:
            if Coupon.objects.filter(code=code).exclude(id=coupon.id).exists():
                error["code"] = "Coupon code is already exist"
            
        if not discount:
            error["discount"] = "Discount is required"
        else:   
            if int(discount) < 10 or int(discount) > 90:
                error["discount"] = "Discount must be in between 10 and 90"
                
        if not min_purchase:
            error["min_purchase"] = "Minimum purchase amount is required"
        else:
            if float(min_purchase) < 100:
                error["min_purchase"] = "Minimum purchase amount must be greater than 100"
        
        if not error:
            coupon.code = code
            coupon.discount = Decimal(discount)
            coupon.min_purchase = Decimal(min_purchase) if min_purchase else None
            coupon.active = active
            coupon.save()
            return redirect("admin_coupon_list")

    return render(request, "custom_admin/coupons/coupon_form.html", {"coupon": coupon, "action": "Edit", "error": error})

@staff_member_required(login_url='admin_login')
def admin_coupon_delete(request, id):
    coupon = get_object_or_404(Coupon, id=id)
    coupon.delete()
    messages.success(request, f'Coupon "{coupon.code}" deleted successfully!')
    return redirect("admin_coupon_list")
