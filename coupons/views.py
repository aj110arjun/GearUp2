from django.shortcuts import redirect, get_object_or_404
from django.utils import timezone
from django.contrib import messages
from .models import Coupon
from .forms import CouponApplyForm

def apply_coupon(request):
    if request.method == "POST":
        form = CouponApplyForm(request.POST)
        if form.is_valid():
            code = form.cleaned_data["code"].strip()
            try:
                coupon = Coupon.objects.get(code__iexact=code)
                if coupon.is_valid():
                    request.session["coupon_id"] = coupon.id  # store coupon in session
                    messages.success(request, f"Coupon '{code}' applied successfully!")
                else:
                    messages.error(request, "This coupon is expired or inactive.")
            except Coupon.DoesNotExist:
                messages.error(request, "Invalid coupon code.")
    return redirect("cart_view")

def remove_coupon(request):
    request.session.pop("coupon_id", None)
    return redirect("cart_view")
