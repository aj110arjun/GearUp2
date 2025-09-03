
from decimal import Decimal
from django.utils.dateparse import parse_datetime
from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import redirect, get_object_or_404, render
from django.utils import timezone
from .models import Coupon
from django.contrib.auth.decorators import login_required
from decimal import Decimal
from cart.models import CartItem
from django.utils.dateparse import parse_date
from django.views.decorators.cache import never_cache


@login_required(login_url="login")
@never_cache
def apply_coupon(request):
    error = {}
    items = CartItem.objects.filter(user=request.user).select_related("variant__product")
    subtotal = sum(item.quantity * item.variant.price for item in items)

    coupon = None
    discount = Decimal("0.00")

    if request.method == "POST":
        code = request.POST.get("code", "").strip()
        if not code:
            error["coupon"] = "Please enter a coupon code."
        else:
            try:
                coupon = Coupon.objects.get(code__iexact=code, active=True)
                now = timezone.now()
                if (coupon.valid_from and coupon.valid_from > now) or (coupon.valid_to and coupon.valid_to < now):
                    error["coupon"] = "This coupon is expired or not yet valid."
                    request.session.pop("coupon_id", None)
                    coupon = None

                elif coupon.min_purchase and subtotal < coupon.min_purchase:
                    error["coupon"] = f"Coupon requires minimum purchase of ₹{coupon.min_purchase}."
                    request.session.pop("coupon_id", None)
                    coupon = None
                else:
                    discount = subtotal * Decimal(coupon.discount) / 100
                    request.session["coupon_id"] = coupon.code

            except Coupon.DoesNotExist:
                error["coupon"] = "Invalid or expired coupon code."
                request.session.pop("coupon_id", None)

    total = subtotal - discount

    return render(
        request,
        "user/cart/cart_view.html",
        {
            "items": items,
            "subtotal": subtotal,
            "discount": discount,
            "total": total,
            "coupon": coupon,
            "error": error,   # ✅ directly passed to template
        },
    )


def remove_coupon(request):
    request.session.pop("coupon_id", None)
    return redirect("cart_view")

@staff_member_required(login_url='admin_login')
@never_cache
def admin_coupon_list(request):
    coupons = Coupon.objects.all().order_by('-valid_from')  # Order by latest
    context = {
        'coupons': coupons,
    }
    return render(request, 'custom_admin/coupons/coupon_list.html', context)

@staff_member_required(login_url='admin_login')
@never_cache
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
@never_cache
def admin_coupon_edit(request, id):
    error = {}
    coupon = get_object_or_404(Coupon, id=id)

    if request.method == "POST":
        code = request.POST.get("code", "").strip()
        discount = request.POST.get("discount")
        min_purchase = request.POST.get("min_purchase")
        valid_from = request.POST.get("valid_from")
        valid_to = request.POST.get("valid_to")
        active = request.POST.get("active") == "on"

        # --- Code Validation ---
        if not code:
            error["code"] = "Coupon code is required"
        elif Coupon.objects.filter(code=code).exclude(id=coupon.id).exists():
            error["code"] = "Coupon code already exists"

        # --- Discount Validation ---
        if not discount:
            error["discount"] = "Discount is required"
        else:
            try:
                discount_val = int(discount)
                if discount_val < 10 or discount_val > 90:
                    error["discount"] = "Discount must be between 10 and 90"
            except ValueError:
                error["discount"] = "Invalid discount value"

        # --- Min Purchase Validation ---
        if not min_purchase:
            error["min_purchase"] = "Minimum purchase amount is required"
        else:
            try:
                min_purchase_val = float(min_purchase)
                if min_purchase_val < 100:
                    error["min_purchase"] = "Minimum purchase must be at least 100"
            except ValueError:
                error["min_purchase"] = "Invalid minimum purchase value"

        # --- Valid From & Valid To ---
        valid_from_dt = parse_datetime(valid_from) if valid_from else None
        valid_to_dt = parse_datetime(valid_to) if valid_to else None

        if valid_from and not valid_from_dt:
            error["valid_from"] = "Invalid date format"
        if valid_to and not valid_to_dt:
            error["valid_to"] = "Invalid date format"
        if valid_from_dt and valid_to_dt and valid_from_dt >= valid_to_dt:
            error["valid_to"] = "Valid To must be after Valid From"

        # --- Save if no errors ---
        if not error:
            coupon.code = code
            coupon.discount = Decimal(discount)
            coupon.min_purchase = Decimal(min_purchase)
            coupon.valid_from = valid_from_dt
            coupon.valid_to = valid_to_dt
            coupon.active = active
            coupon.save()
            return redirect("admin_coupon_list")

    return render(
        request,
        "custom_admin/coupons/coupon_form.html",
        {"coupon": coupon, "action": "Edit", "error": error},
    )

@staff_member_required(login_url='admin_login')
@never_cache
def admin_coupon_delete(request, id):
    coupon = get_object_or_404(Coupon, id=id)
    coupon.delete()
    messages.success(request, f'Coupon "{coupon.code}" deleted successfully!')
    return redirect("admin_coupon_list")
