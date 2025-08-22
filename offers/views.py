from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib import messages
from products.models import Product, Category, ProductOffer, CategoryOffer
from datetime import date
from django.utils.dateparse import parse_date


# ---------------- Product Offers ---------------- #
@staff_member_required(login_url="admin_login")
def admin_product_offers(request):
    offers = ProductOffer.objects.select_related("product").order_by("-start_date")
    return render(request, "custom_admin/offers/product_offers.html", {"offers": offers})


@staff_member_required(login_url="admin_login")
def admin_add_product_offer(request):
    if request.method == "POST":
        product_id = request.POST.get("product")
        discount = request.POST.get("discount")
        start_date = request.POST.get("start_date")
        end_date = request.POST.get("end_date")
        active = request.POST.get("active") == "on"

        if not product_id or not discount:
            messages.error(request, "Please fill in all required fields.")
            return redirect("admin_add_product_offer")

        product = get_object_or_404(Product, id=product_id)
        ProductOffer.objects.create(
            product=product,
            discount_percent=discount,
            start_date=start_date,
            end_date=end_date,
            active=active,
        )
        messages.success(request, f"Offer added for {product.name}")
        return redirect("admin_product_offers")

    products = Product.objects.all()
    return render(request, "custom_admin/offers/add_product_offer.html", {"products": products})


@staff_member_required(login_url="admin_login")
def admin_delete_product_offer(request, offer_id):
    offer = get_object_or_404(ProductOffer, id=offer_id)
    offer.delete()
    messages.success(request, "Product offer deleted successfully.")
    return redirect("admin_product_offers")


# ---------------- Category Offers ---------------- #
@staff_member_required(login_url="admin_login")
def admin_category_offers(request):
    offers = CategoryOffer.objects.select_related("category").order_by("-start_date")
    return render(request, "custom_admin/offers/category_offers.html", {"offers": offers})


@staff_member_required(login_url="admin_login")
def admin_add_category_offer(request):
    if request.method == "POST":
        category_id = request.POST.get("category")
        discount = request.POST.get("discount")
        start_date = request.POST.get("start_date")
        end_date = request.POST.get("end_date")
        active = request.POST.get("active") == "on"

        if not category_id or not discount:
            messages.error(request, "Please fill in all required fields.")
            return redirect("admin_add_category_offer")

        category = get_object_or_404(Category, id=category_id)
        CategoryOffer.objects.create(
            category=category,
            discount_percent=discount,
            start_date=start_date,
            end_date=end_date,
            active=active,
        )
        messages.success(request, f"Offer added for {category.name}")
        return redirect("admin_category_offers")

    categories = Category.objects.all()
    return render(request, "custom_admin/offers/add_category_offer.html", {"categories": categories})


@staff_member_required(login_url="admin_login")
def admin_delete_category_offer(request, offer_id):
    offer = get_object_or_404(CategoryOffer, id=offer_id)
    offer.delete()
    messages.success(request, "Category offer deleted successfully.")
    return redirect("admin_category_offers")

@staff_member_required(login_url="admin_login")
def admin_product_offer_edit(request, product_id):
    # fetch product by UUID
    product = get_object_or_404(Product, product_id=product_id)
    # get the related offer
    offer = get_object_or_404(ProductOffer, product=product)

    if request.method == "POST":
        # re-select product from dropdown (UUID)
        product_uuid = request.POST.get("product")
        if product_uuid:
            offer.product = get_object_or_404(Product, product_id=product_uuid)

        # update offer fields
        offer.discount_percent = int(request.POST.get("discount_percent") or 0)
        offer.active = request.POST.get("active") == "on"
        offer.start_date = parse_date(request.POST.get("start_date")) if request.POST.get("start_date") else None
        offer.end_date = parse_date(request.POST.get("end_date")) if request.POST.get("end_date") else None

        offer.save()
        messages.success(request, f"Offer updated for {offer.product.name}")
        return redirect("admin_product_offers")

    products = Product.objects.all()
    return render(
        request,
        "custom_admin/offers/product_offer_edit.html",
        {"offer": offer, "products": products}
    )
    
@staff_member_required(login_url="admin_login")
def admin_category_offer_edit(request, category_id):
    category = get_object_or_404(Category, id=category_id)
    offer = get_object_or_404(CategoryOffer, category=category)

    if request.method == "POST":
        category_id = request.POST.get("category")
        offer.category = get_object_or_404(Category, id=category_id)
        offer.discount_percent = request.POST.get("discount")
        offer.start_date = request.POST.get("start_date")
        offer.end_date = request.POST.get("end_date")
        offer.active = request.POST.get("active") == "on"
        offer.save()
        messages.success(request, "Category offer updated successfully.")
        return redirect("admin_category_offers")

    categories = Category.objects.all()
    return render(request, "custom_admin/offers/category_offer_edit.html", {"categories": categories, "offer": offer})

