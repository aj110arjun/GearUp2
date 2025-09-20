from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib import messages
from products.models import Product, Category, ProductOffer, CategoryOffer
from datetime import date
from django.utils.dateparse import parse_date
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
        if ProductOffer.objects.filter(product=product_id).exists():
            error['product'] = "Offer on this product already exist"

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
    return render(
        request,
        "custom_admin/offers/add_product_offer.html",
        {"products": products, "error": error, "form_data": form_data}
    )



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
        if CategoryOffer.objects.filter(category = category_id).exists():
            error['category'] = "Offer on this category already exist"

        if not error:
            category = get_object_or_404(Category, id=category_id)
            CategoryOffer.objects.create(
                category=category,
                discount_percent=discount,
                start_date=start_date,
                end_date=end_date,
                active=active,
            )
            return redirect("admin_category_offers")

    categories = Category.objects.all()
    return render(request, "custom_admin/offers/add_category_offer.html", {
        "categories": categories,
        "error": error,
        "form_data": form_data
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
def admin_product_offer_edit(request, product_id):
    # fetch product by UUID
    product = get_object_or_404(Product, product_id=product_id)
    # get the related offer
    offer = get_object_or_404(ProductOffer, product=product)

    if request.method == "POST":
        error={}
        product_uuid = request.POST.get("product")

        discount = request.POST.get("discount_percent")
        start_date = request.POST.get("start_date")
        end_date = request.POST.get("end_date")

        if product_uuid:
            offer.product = get_object_or_404(Product, product_id=product_uuid)
            
        if ProductOffer.objects.filter(product=offer.product).exclude(id=offer.id).exists():
            error['product'] = "Offer in the product already exist"

        if not discount:
            error['discount'] = "Discount is required"
        elif int(discount) < 10 or int(discount) > 90:
            error['discount'] = "Discount must in between 10 and 90"

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
        return render(request,"custom_admin/offers/product_offer_edit.html",{"offer": offer,"error":error, "products": Product.objects.all()})
        
    products = Product.objects.all()
    context = {
        "offer": offer,
        "products": products,
        }
    return render(request,"custom_admin/offers/product_offer_edit.html",context)
    
@staff_member_required(login_url="admin_login")
@never_cache
def admin_category_offer_edit(request, category_id):
    error={}
    category = get_object_or_404(Category, id=category_id)
    offer = get_object_or_404(CategoryOffer, category=category)

    if request.method == "POST":
        category_id = request.POST.get("category")
        new_category = get_object_or_404(Category, id=category_id)
        discount = request.POST.get("discount")

        if CategoryOffer.objects.filter(category=new_category).exclude(id=offer.id).exists():
            error['category'] = "Offer on this category already exist"

        if int(discount) < 10 or int(discount) > 90:
            error['discount'] = "Discount must in between 10 and 20"

        if not error:
            category_id = request.POST.get("category")
            offer.category = get_object_or_404(Category, id=category_id)
            offer.discount_percent = request.POST.get("discount")
            offer.start_date = request.POST.get("start_date")
            offer.end_date = request.POST.get("end_date")
            offer.active = request.POST.get("active") == "on"
            offer.save()
            return redirect("admin_category_offers")

        return render(request,"custom_admin/offers/category_offer_edit.html",{"offer": offer,"error":error, "categories": Category.objects.all()})
        
    categories = Category.objects.all()
    return render(request, "custom_admin/offers/category_offer_edit.html", {"categories": categories, "offer": offer})

