from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib import messages
from products.models import Product, Category, ProductOffer, CategoryOffer
from datetime import date
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
            error['product'] = "Product field required"
        if not discount:
            error['discount'] = "Discount field is required"
        elif int(discount) < 10 or int(discount) > 90:
            error['discount'] = "Discount must be in between 10 and 90"
        if not start_date:
            error['start_date'] = "Start date is required"
        if not end_date:
            error['end_date'] = "End date is required"

        # Only check for offer overlap if no earlier errors and dates are present
        if not error and product_id and start_date and end_date:
            overlap_offers = ProductOffer.objects.filter(
                product=product_id,
                start_date__lte=end_date,
                end_date__gte=start_date
            )
            if overlap_offers.exists():
                error['product'] = "Offer on this product overlaps with existing offer periods"

        if not error:
            product = get_object_or_404(Product, id=product_id)
            ProductOffer.objects.create(
                product=product,
                discount_percent=discount,
                start_date=start_date,
                end_date=end_date,
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

        if product_uuid:
            offer.product = get_object_or_404(Product, product_id=product_uuid)

        # Validate overlapping offers for the same product excluding this offer
        if start_date and end_date and offer.product:
            overlap_offers = ProductOffer.objects.filter(
                product=offer.product,
                start_date__lte=end_date,
                end_date__gte=start_date
            ).exclude(id=offer.id)

            if overlap_offers.exists():
                error['product'] = "Another offer on this product overlaps with the selected dates."

        if not discount:
            error['discount'] = "Discount is required"
        elif int(discount) < 10 or int(discount) > 90:
            error['discount'] = "Discount must be between 10 and 90"

        if not start_date:
            error['start_date'] = "Start date is required"

        if not end_date:
            error['end_date'] = "End date is required"

        if not error:
            offer.discount_percent = int(discount or 0)
            offer.active = request.POST.get("active") == "on"
            offer.start_date = parse_date(start_date) if start_date else None
            offer.end_date = parse_date(end_date) if end_date else None

            offer.save()
            return redirect("admin_product_offers")

        return render(
            request,
            "custom_admin/offers/product_offer_edit.html",
            {"offer": offer, "error": error, "products": Product.objects.all()}
        )

    products = Product.objects.all()
    context = {
        "offer": offer,
        "products": products,
        "today": localdate().isoformat(),
    }
    return render(request, "custom_admin/offers/product_offer_edit.html", context)

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

        form_data = {
            "category": category_id,
            "discount": discount,
            "start_date": start_date,
            "end_date": end_date,
            "active": active,
        }

        # Basic validations
        if not category_id:
            error['category'] = "Category is required"
        if not discount:
            error['discount'] = "Discount is required"
        elif int(discount) < 10 or int(discount) > 90:
            error['discount'] = "Discount must be in between 10 and 90"
        if not start_date:
            error['start_date'] = "Start date is required"
        if not end_date:
            error['end_date'] = "End date is required"

        # Date overlap validation on category offers
        if not error and category_id and start_date and end_date:
            overlap_offers = CategoryOffer.objects.filter(
                category=category_id,
                start_date__lte=end_date,
                end_date__gte=start_date
            )
            if overlap_offers.exists():
                error['category'] = "Offer on this category overlaps with existing offer periods"

        if not error:
            category = get_object_or_404(Category, id=category_id)
            CategoryOffer.objects.create(
                category=category,
                discount_percent=int(discount),
                start_date=start_date,
                end_date=end_date,
                active=active,
            )
            return redirect("admin_category_offers")

    categories = Category.objects.all()
    return render(request, "custom_admin/offers/add_category_offer.html", {
        "categories": categories,
        "error": error,
        "form_data": form_data,
        "today": localdate().isoformat(),
    })

@staff_member_required(login_url="admin_login")
@never_cache
def admin_delete_category_offer(request, offer_id):
    offer = get_object_or_404(CategoryOffer, id=offer_id)
    offer.delete()
    messages.success(request, "Category offer deleted successfully.")
    return redirect("admin_category_offers")

@staff_member_required(login_url="admin_login")
@never_cache
def admin_category_offer_edit(request, category_id):
    error = {}
    category = get_object_or_404(Category, id=category_id)
    
    # Fetch the specific offer by category; if multiple offers per category exist, consider using offer ID for uniqueness
    offer = get_object_or_404(CategoryOffer, category=category)

    if request.method == "POST":
        category_id_post = request.POST.get("category")
        new_category = get_object_or_404(Category, id=category_id_post)
        discount = request.POST.get("discount")
        start_date = request.POST.get("start_date")
        end_date = request.POST.get("end_date")
        active = request.POST.get("active") == "on"

        # Validate date overlap excluding current offer
        if start_date and end_date:
            overlapping_offers = CategoryOffer.objects.filter(
                category=new_category,
                start_date__lte=end_date,
                end_date__gte=start_date
            ).exclude(id=offer.id)

            if overlapping_offers.exists():
                error['category'] = "Offer on this category overlaps with existing offer periods"

        # Validate discount range
        if discount:
            try:
                disc_val = int(discount)
                if disc_val < 10 or disc_val > 90:
                    error['discount'] = "Discount must be between 10 and 90"
            except ValueError:
                error['discount'] = "Discount must be a valid number"
        else:
            error['discount'] = "Discount is required"

        if not start_date:
            error['start_date'] = "Start date is required"
        if not end_date:
            error['end_date'] = "End date is required"

        if not error:
            offer.category = new_category
            offer.discount_percent = disc_val
            offer.start_date = parse_date(start_date)
            offer.end_date = parse_date(end_date)
            offer.active = active
            offer.save()
            return redirect("admin_category_offers")

        return render(request, "custom_admin/offers/category_offer_edit.html", {
            "offer": offer,
            "error": error,
            "categories": Category.objects.all(),
            "today": localdate().isoformat()
        })

    categories = Category.objects.all()
    return render(request, "custom_admin/offers/category_offer_edit.html", {
        "categories": categories,
        "offer": offer,
        "today": localdate().isoformat()
    })

