from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.views.decorators.cache import never_cache
from django.utils.dateparse import parse_date
from django.http import JsonResponse
from django.db.models import Q
from django.views.decorators.http import require_GET
from decimal import Decimal
from products.models import Product

from coupons.models import Coupon


# ----------------- Admin: List Coupons -----------------
@staff_member_required(login_url="admin_login")
@never_cache
def admin_coupon_list(request):
    coupons = Coupon.objects.all().order_by("-valid_from")
    return render(request, "custom_admin/coupons/coupon_list.html", {"coupons": coupons})


# ----------------- Admin: Add Coupon -----------------
@staff_member_required(login_url="admin_login")
@never_cache
def admin_coupon_add(request):
    errors = {}
    products = Product.objects.all()  # <-- Pass all products

    if request.method == "POST":
        # Get form data
        code = request.POST.get("code", "").strip().upper()
        discount_value = request.POST.get("discount_value")
        active = request.POST.get("active") == "on"
        valid_from_str = request.POST.get("valid_from")
        valid_to_str = request.POST.get("valid_to")
        usage_limit_total = request.POST.get("usage_limit_total") or 0
        usage_limit_per_user = request.POST.get("usage_limit_per_user") or 0
        selected_products = request.POST.getlist("products")  # <-- Get selected products

        # Validation
        if not code:
            errors["code"] = "Coupon code is required."
        if not discount_value:
            errors["discount_value"] = "Discount value is required."
        if not valid_from_str:
            errors["valid_from"] = "Start date is required."
        if not valid_to_str:
            errors["valid_to"] = "End date is required."
        if int(usage_limit_per_user) < 0:
            errors["usage_limit_per_user"] = "Usage limit per user cannot be negative."
        if int(usage_limit_total) < 0:
            errors["usage_limit_total"] = "Total usage limit cannot be negative."
        if Coupon.objects.filter(code=code).exists():
            errors["code"] = "Coupon code must be unique."

        try:
            discount_value_num = float(discount_value)
            if discount_value_num <= 0:
                errors["discount_value"] = "Discount value must be greater than 0."
        except (TypeError, ValueError):
            errors["discount_value"] = "Discount value must be a valid number."

        # Date parsing
        valid_from = parse_date(valid_from_str) if valid_from_str else None
        valid_to = parse_date(valid_to_str) if valid_to_str else None

        if valid_from and valid_to and valid_to < valid_from:
            errors['valid_to'] = "End date cannot be before start date."

        if errors:
            coupon_data = {
                "code": code,
                "discount_value": discount_value,
                "active": active,
                "valid_from": valid_from,
                "valid_to": valid_to,
                "usage_limit_total": usage_limit_total,
                "usage_limit_per_user": usage_limit_per_user,
                "products": [int(pid) for pid in selected_products],  # Keep selected products
            }
            context = {
                "action": "Add",
                "coupon": coupon_data,
                "error": errors,
                "products": products,
            }
            return render(request, "custom_admin/coupons/coupon_form.html", context)

        # Create coupon
        coupon = Coupon.objects.create(
            code=code,
            discount_value=discount_value,
            active=active,
            valid_from=valid_from,
            valid_to=valid_to,
            usage_limit_total=usage_limit_total,
            usage_limit_per_user=usage_limit_per_user
        )

        # Assign selected products
        if selected_products:
            coupon.products.set(selected_products)

        messages.success(request, f"Coupon '{coupon.code}' created successfully.")
        return redirect("admin_coupon_list")

    context = {
        "action": "Add",
        "products": products  # Pass products for initial form
    }
    return render(request, "custom_admin/coupons/coupon_form.html", context)


# ----------------- Admin: Edit Coupon -----------------
@staff_member_required(login_url="admin_login")
@never_cache
def admin_coupon_edit(request, coupon_id):
    coupon = get_object_or_404(Coupon, id=coupon_id)

    if request.method == "POST":
        code = request.POST.get("code", "").strip().upper()
        discount_value = request.POST.get("discount_value")
        active = request.POST.get("active") == "on"
        valid_from_str = request.POST.get("valid_from")
        valid_to_str = request.POST.get("valid_to")
        usage_limit_total = request.POST.get("usage_limit_total") or 0
        usage_limit_per_user = request.POST.get("usage_limit_per_user") or 0

        # Validation
        errors = {}
        if not code:
            errors["code"] = "Coupon code is required."
        if not discount_value:
            errors["discount_value"] = "Discount value is required."
        if not valid_from_str:
            errors["valid_from"] = "Start date is required."
        if not valid_to_str:
            errors["valid_to"] = "End date is required."

        try:
            discount_value_num = float(discount_value)
            if discount_value_num <= 0:
                errors["discount_value"] = "Discount value must be greater than 0."
        except (TypeError, ValueError):
            errors["discount_value"] = "Discount value must be a valid number."

        valid_from = parse_date(valid_from_str) if valid_from_str else None
        valid_to = parse_date(valid_to_str) if valid_to_str else None

        if valid_from and valid_to and valid_to < valid_from:
            errors['valid_to'] = "End date cannot be before start date."

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
        coupon.discount_value = discount_value
        coupon.active = active
        coupon.valid_from = valid_from
        coupon.valid_to = valid_to
        coupon.usage_limit_total = usage_limit_total
        coupon.usage_limit_per_user = usage_limit_per_user
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
    code = request.GET.get("code", "").strip().upper()
    
    if request.headers.get("x-requested-with") == "XMLHttpRequest":
        try:
            coupon = Coupon.objects.get(code=code, active=True)

            if coupon.can_user_use(request.user):
                # Save coupon code in session
                request.session["coupon_id"] = coupon.code

                # Calculate discount
                cart_items = request.user.cart_items.select_related("variant__product")
                subtotal = sum(item.variant.get_discounted_price() * item.quantity for item in cart_items)
                discount = coupon.discount_value
                grand_total = max(subtotal - discount, 0)

                return JsonResponse({
                    "success": True,
                    "code": coupon.code,
                    "discount": discount,
                    "new_total": grand_total
                })
            else:
                return JsonResponse({"success": False, "message": "Coupon is invalid or already used."})
        except Coupon.DoesNotExist:
            return JsonResponse({"success": False, "message": "Coupon does not exist."})
    return JsonResponse({"success": False, "message": "Invalid request."})


# ----------------- User: Remove Coupon -----------------
@login_required(login_url="login")
@never_cache
def remove_coupon(request):
    if "coupon_id" in request.session:
        del request.session["coupon_id"]
        messages.success(request, "Coupon removed successfully.")
    return redirect("checkout")
