from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from .models import Address
from django.contrib import messages
from django.views.decorators.cache import never_cache
from django.urls import reverse


@login_required(login_url='login')
@never_cache
def address_list(request):
    addresses = request.user.addresses.all()
    breadcrumbs = [
        ("Home", reverse("home")),
        ("Account", reverse("account_info")),
        ("My Address", None),
    ]
    context = {
        "breadcrumbs": breadcrumbs,
        "addresses": addresses
    }
    return render(request, "user/address/address_list.html", context)

@login_required(login_url='login')
@never_cache
def add_address(request):
    if request.method == "POST":
        full_name = request.POST.get("full_name")
        phone = request.POST.get("phone")
        address_line_1 = request.POST.get("address_line_1")
        address_line_2 = request.POST.get("address_line_2")
        city = request.POST.get("city")
        state = request.POST.get("state")
        postal_code = request.POST.get("postal_code")
        country = request.POST.get("country", "India")
        is_default = bool(request.POST.get("is_default"))

        if full_name and phone and address_line_1 and city and state and postal_code:
            address =  Address.objects.create(
                user=request.user,
                full_name=full_name,
                phone=phone,
                address_line_1=address_line_1,
                address_line_2=address_line_2,
                city=city,
                state=state,
                postal_code=postal_code,
                country=country,
                is_default=is_default
            )
            request.session['last_address_id'] = address.id
            next_url = request.POST.get('next') or request.GET.get('next')
            if next_url:
                return redirect(next_url)
            return redirect("address_list")
        else:
            error = "All required fields must be filled."
            return render(request, "user/address/address_form.html", {"error": error})
        
    breadcrumbs = [
        ("Home", reverse("home")),
        ("Account", reverse("account_info")),
        ("My Address", reverse("address_list")),
        ("Add Address", None),
    ]
    
    context = {"breadcrumbs": breadcrumbs}

    return render(request, "user/address/address_form.html", context)

@login_required(login_url='login')
@never_cache
def edit_address(request, pk):
    address = get_object_or_404(Address, pk=pk, user=request.user)

    if request.method == "POST":
        address.full_name = request.POST.get("full_name")
        address.phone = request.POST.get("phone")
        address.address_line_1 = request.POST.get("address_line_1")
        address.address_line_2 = request.POST.get("address_line_2")
        address.city = request.POST.get("city")
        address.state = request.POST.get("state")
        address.postal_code = request.POST.get("postal_code")
        address.country = request.POST.get("country", "India")
        address.is_default = bool(request.POST.get("is_default"))
        address.save()
        
        next_url = request.POST.get("next") or request.GET.get("next")
        if next_url:
            return redirect(next_url)
        
        return redirect("address_list")
    breadcrumbs = [
        ("Home", reverse("home")),
        ("Account", reverse("account_info")),
        ("My Address", reverse("address_list")),
        ("Edit Address", None),
    ]

    context = {
        "breadcrumbs": breadcrumbs,
        "address": address
    }

    return render(request, "user/address/address_form.html", context)

def set_default_address(request, pk):
    address = get_object_or_404(Address, pk=pk, user=request.user)

    Address.objects.filter(user=request.user, is_default=True).update(is_default=False)
    address.is_default = True
    address.save()

    next_url = request.POST.get("next") or request.GET.get("next")
    if next_url:
        return redirect(next_url)
    return redirect("address_list")

@login_required(login_url='login')
@never_cache
def delete_address(request, pk):
    address = get_object_or_404(Address, pk=pk, user=request.user)  # ✅ Fetch first

    if address.is_default:
        messages.error(request, "You cannot delete your default address.")
        return redirect("address_list")

    address.delete()
    next_url = request.POST.get("next") or request.GET.get("next")
    if next_url:
        return redirect(next_url)
    return redirect("address_list")

