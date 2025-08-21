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

        if not code or not discount:
            messages.error(request, "Please fill all required fields.")
            return redirect("admin_coupon_add")

        # Create the coupon
        coupon = Coupon.objects.create(
            code=code,
            discount=Decimal(discount),
            min_purchase=Decimal(min_purchase) if min_purchase else None,
            active=active,
            valid_from=valid_from,
            valid_to=valid_to
        )
        messages.success(request, f'Coupon "{coupon.code}" created successfully!')
        return redirect("admin_coupon_list")

    return render(request, "custom_admin/coupons/coupon_form.html", {"action": "Add"})

@staff_member_required(login_url='admin_login')
def admin_coupon_edit(request, id):
    coupon = get_object_or_404(Coupon, id=id)

    if request.method == "POST":
        code = request.POST.get("code").strip()
        discount = request.POST.get("discount")
        min_purchase = request.POST.get("min_purchase") or None
        active = request.POST.get("active") == "on"

        if not code or not discount:
            messages.error(request, "Please fill all required fields.")
            return redirect("admin_coupon_edit", id=id)

        coupon.code = code
        coupon.discount = Decimal(discount)
        coupon.min_purchase = Decimal(min_purchase) if min_purchase else None
        coupon.active = active
        coupon.save()

        messages.success(request, f'Coupon "{coupon.code}" updated successfully!')
        return redirect("admin_coupon_list")

    return render(request, "custom_admin/coupons/coupon_form.html", {"coupon": coupon, "action": "Edit"})

@staff_member_required(login_url='admin_login')
def admin_coupon_delete(request, id):
    coupon = get_object_or_404(Coupon, id=id)
    coupon.delete()
    messages.success(request, f'Coupon "{coupon.code}" deleted successfully!')
    return redirect("admin_coupon_list")
