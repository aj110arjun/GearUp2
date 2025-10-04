from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib import messages
from products.models import Product, Category, ProductOffer, CategoryOffer
from datetime import date, datetime
from django.utils.dateparse import parse_date
from django.utils.timezone import localdate
from django.views.decorators.cache import never_cache


# ---------------- Product Offers ---------------- #
@staff_member_required(login_url="admin_login")
@never_cache
def admin_product_offers(request):
    offers = ProductOffer.objects.select_related("product").order_by("-start_date")
    return render(request, "custom_admin/offers/product_offers.html", {"offers": offers})


@staff_member_required(login_url="admin_login")
@never_cache
def admin_add_product_offer(request):
    error = {}
    form_data = {
        "product": "",
        "discount": "",
        "start_date": "",
        "end_date": "",
        "active": False,
    }

    if request.method == "POST":
        product_id = request.POST.get("product")
        discount = request.POST.get("discount")
        start_date = request.POST.get("start_date")
        end_date = request.POST.get("end_date")
        active = request.POST.get("active") == "on"

        # Preserve user input
        form_data = {
            "product": product_id,
            "discount": discount,
            "start_date": start_date,
            "end_date": end_date,
            "active": active,
        }

        # Basic validation
        if not product_id:
            error['product'] = "Product field is required"
        if not discount:
            error['discount'] = "Discount field is required"
        elif int(discount) < 10 or int(discount) > 90:
            error['discount'] = "Discount must be between 10 and 90"
        if not start_date:
            error['start_date'] = "Start date is required"
        if not end_date:
            error['end_date'] = "End date is required"

        # ✅ Date validation
        if start_date and end_date:
            try:
                start_date_obj = datetime.strptime(start_date, "%Y-%m-%d").date()
                end_date_obj = datetime.strptime(end_date, "%Y-%m-%d").date()

                if start_date_obj > end_date_obj:
                    error['end_date'] = "End date must be greater than or equal to start date"
                else:
                    # ✅ Overlap validation (only check if product selected)
                    if product_id:
                        overlap_offers = ProductOffer.objects.filter(
                            product_id=product_id,
                            start_date__lte=end_date_obj,
                            end_date__gte=start_date_obj,
                        )
                        if overlap_offers.exists():
                            error['product'] = "Another offer on this product overlaps with the selected dates."
            except ValueError:
                error['date'] = "Invalid date format"

        # ✅ If no errors, save offer
        if not error:
            product = get_object_or_404(Product, id=product_id)
            ProductOffer.objects.create(
                product=product,
                discount_percent=int(discount),
                start_date=start_date_obj,
                end_date=end_date_obj,
                active=active,
            )
            return redirect("admin_product_offers")

    products = Product.objects.all()

    context = {
        "products": products,
        "error": error,
        "form_data": form_data,
        "today": localdate().isoformat(),
    }

    return render(request, "custom_admin/offers/add_product_offer.html", context)


@staff_member_required(login_url="admin_login")
@never_cache
def admin_product_offer_edit(request, product_id):
    offer = get_object_or_404(ProductOffer, id=product_id)

    if request.method == "POST":
        error = {}
        product_uuid = request.POST.get("product")
        discount = request.POST.get("discount_percent")
        start_date = request.POST.get("start_date")
        end_date = request.POST.get("end_date")
        active = request.POST.get("active") == "on"

        # ✅ Assign product if changed
        if product_uuid:
            offer.product = get_object_or_404(Product, product_id=product_uuid)

        # ✅ Discount validation
        if not discount:
            error['discount'] = "Discount is required"
        else:
            try:
                disc_val = int(discount)
                if disc_val < 10 or disc_val > 90:
                    error['discount'] = "Discount must be between 10 and 90"
            except ValueError:
                error['discount'] = "Discount must be a valid number"

        # ✅ Date required check
        if not start_date:
            error['start_date'] = "Start date is required"
        if not end_date:
            error['end_date'] = "End date is required"

        # ✅ Date parsing + comparison
        start_date_obj = None
        end_date_obj = None
        if start_date and end_date:
            try:
                start_date_obj = datetime.strptime(start_date, "%Y-%m-%d").date()
                end_date_obj = datetime.strptime(end_date, "%Y-%m-%d").date()

                if start_date_obj > end_date_obj:
                    error['end_date'] = "End date must be greater than or equal to start date"

                # ✅ Overlap validation (excluding current offer)
                if offer.product and not error:
                    overlap_offers = ProductOffer.objects.filter(
                        product=offer.product,
                        start_date__lte=end_date_obj,
                        end_date__gte=start_date_obj
                    ).exclude(id=offer.id)

                    if overlap_offers.exists():
                        error['product'] = "Another offer overlaps with the selected dates."

            except ValueError:
                error['date'] = "Invalid date format. Use YYYY-MM-DD."

        # ✅ Save if no errors
        if not error:
            offer.discount_percent = disc_val
            offer.active = active
            offer.start_date = start_date_obj
            offer.end_date = end_date_obj
            offer.save()
            return redirect("admin_product_offers")

        return render(
            request,
            "custom_admin/offers/product_offer_edit.html",
            {
                "offer": offer,
                "error": error,
                "products": Product.objects.all(),
                "today": localdate().isoformat()
            }
        )

    # GET request
    return render(request, "custom_admin/offers/product_offer_edit.html", {
        "offer": offer,
        "products": Product.objects.all(),
        "today": localdate().isoformat(),
    })

@staff_member_required(login_url="admin_login")
@never_cache
def admin_delete_product_offer(request, offer_id):
    offer = get_object_or_404(ProductOffer, id=offer_id)
    offer.delete()
    messages.success(request, "Product offer deleted successfully.")
    return redirect("admin_product_offers")


# ---------------- Category Offers ---------------- #
@staff_member_required(login_url="admin_login")
@never_cache
def admin_category_offers(request):
    offers = CategoryOffer.objects.select_related("category").order_by("-start_date")
    return render(request, "custom_admin/offers/category_offers.html", {"offers": offers})


@staff_member_required(login_url="admin_login")
@never_cache
def admin_add_category_offer(request):
    error = {}
    form_data = {
        "category": "",
        "discount": "",
        "start_date": "",
        "end_date": "",
        "active": False,
    }

    if request.method == "POST":
        category_id = request.POST.get("category")
        discount = request.POST.get("discount")
        start_date = request.POST.get("start_date")
        end_date = request.POST.get("end_date")
        active = request.POST.get("active") == "on"

        # Preserve form data
        form_data = {
            "category": category_id,
            "discount": discount,
            "start_date": start_date,
            "end_date": end_date,
            "active": active,
        }

        # ✅ Basic validations
        if not category_id:
            error['category'] = "Category is required"
        if not discount:
            error['discount'] = "Discount is required"
        elif int(discount) < 10 or int(discount) > 90:
            error['discount'] = "Discount must be between 10 and 90"
        if not start_date:
            error['start_date'] = "Start date is required"
        if not end_date:
            error['end_date'] = "End date is required"

        # ✅ Date range + Overlap validation
        if start_date and end_date:
            try:
                start_date_obj = datetime.strptime(start_date, "%Y-%m-%d").date()
                end_date_obj = datetime.strptime(end_date, "%Y-%m-%d").date()

                if start_date_obj > end_date_obj:
                    error['end_date'] = "End date must be greater than or equal to start date"
                else:
                    # ✅ Overlap check
                    if category_id:
                        overlap_offers = CategoryOffer.objects.filter(
                            category_id=category_id,
                            start_date__lte=end_date_obj,
                            end_date__gte=start_date_obj,
                        )
                        if overlap_offers.exists():
                            error['category'] = "Another offer for this category overlaps with the selected dates."
            except ValueError:
                error['date'] = "Invalid date format"

        # ✅ Save if no errors
        if not error:
            category = get_object_or_404(Category, id=category_id)
            CategoryOffer.objects.create(
                category=category,
                discount_percent=int(discount),
                start_date=start_date_obj,
                end_date=end_date_obj,
                active=active,
            )
            return redirect("admin_category_offers")

    categories = Category.objects.all()
    return render(
        request,
        "custom_admin/offers/add_category_offer.html",
        {
            "categories": categories,
            "error": error,
            "form_data": form_data,
            "today": localdate().isoformat(),
        }
    )

@staff_member_required(login_url="admin_login")
@never_cache
def admin_delete_category_offer(request, offer_id):
    offer = get_object_or_404(CategoryOffer, id=offer_id)
    offer.delete()
    messages.success(request, "Category offer deleted successfully.")
    return redirect("admin_category_offers")

@staff_member_required(login_url="admin_login")
@never_cache
def admin_category_offer_edit(request, category_id, start_date):
    error = {}

    # ✅ Get the Category (UUID)
    category = get_object_or_404(Category, id=category_id)

    # ✅ Parse start_date from URL
    try:
        start_date_obj_url = datetime.strptime(start_date, "%Y-%m-%d").date()
    except ValueError:
        return render(request, "custom_admin/offers/category_offer_edit.html", {
            "error": {"date": "Invalid start date in URL"},
            "categories": Category.objects.all(),
            "today": localdate().isoformat()
        })

    # ✅ Unique lookup using category + start_date
    offer = get_object_or_404(
        CategoryOffer.objects.select_related("category"),
        category=category,
        start_date=start_date_obj_url
    )

    if request.method == "POST":
        category_id_post = request.POST.get("category")
        new_category = get_object_or_404(Category, id=category_id_post)
        discount = request.POST.get("discount")
        start_date = request.POST.get("start_date")
        end_date = request.POST.get("end_date")
        active = request.POST.get("active") == "on"

        # ✅ Validate discount
        disc_val = None
        if discount:
            try:
                disc_val = int(discount)
                if disc_val < 10 or disc_val > 90:
                    error['discount'] = "Discount must be between 10 and 90"
            except ValueError:
                error['discount'] = "Discount must be a valid number"
        else:
            error['discount'] = "Discount is required"

        # ✅ Validate required fields
        if not start_date:
            error['start_date'] = "Start date is required"
        if not end_date:
            error['end_date'] = "End date is required"

        # ✅ Date range + Overlap validation
        if start_date and end_date:
            try:
                start_date_obj = datetime.strptime(start_date, "%Y-%m-%d").date()
                end_date_obj = datetime.strptime(end_date, "%Y-%m-%d").date()

                if start_date_obj > end_date_obj:
                    error['end_date'] = "End date must be greater than or equal to start date"
                else:
                    overlapping_offers = CategoryOffer.objects.filter(
                        category=new_category,
                        start_date__lte=end_date_obj,
                        end_date__gte=start_date_obj
                    ).exclude(id=offer.id)

                    if overlapping_offers.exists():
                        conflict = overlapping_offers.first()
                        error['category'] = (
                            f"Another offer overlaps for this category: "
                            f"{conflict.start_date} → {conflict.end_date}"
                        )
            except ValueError:
                error['date'] = "Invalid date format"

        # ✅ Save if no errors
        if not error:
            offer.category = new_category
            offer.discount_percent = disc_val
            offer.start_date = start_date_obj
            offer.end_date = end_date_obj
            offer.active = active
            offer.save()
            return redirect("admin_category_offers")

        return render(request, "custom_admin/offers/category_offer_edit.html", {
            "offer": offer,
            "error": error,
            "categories": Category.objects.all(),
            "today": localdate().isoformat()
        })

    # GET request
    return render(request, "custom_admin/offers/category_offer_edit.html", {
        "categories": Category.objects.all(),
        "offer": offer,
        "today": localdate().isoformat()
    })