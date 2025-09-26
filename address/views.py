from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from .models import Address
from django.contrib import messages
from django.views.decorators.cache import never_cache


@login_required(login_url='login')
@never_cache
def address_list(request):
    addresses = request.user.addresses.all()
    return render(request, "user/address/address_list.html", {"addresses": addresses})

import re

@login_required(login_url='login')
@never_cache
def add_address(request):
    error = {}
    form_data = {
        "full_name": "",
        "phone": "",
        "address_line_1": "",
        "address_line_2": "",
        "city": "",
        "state": "",
        "postal_code": "",
        "country": "India",
        "is_default": False,
    }

    if request.method == "POST":
        full_name = request.POST.get("full_name", "").strip()
        phone = request.POST.get("phone", "").strip()
        address_line_1 = request.POST.get("address_line_1", "").strip()
        address_line_2 = request.POST.get("address_line_2", "").strip()
        city = request.POST.get("city", "").strip()
        state = request.POST.get("state", "").strip()
        postal_code = request.POST.get("postal_code", "").strip()
        country = request.POST.get("country", "India").strip()
        is_default = bool(request.POST.get("is_default"))

        form_data.update({
            "full_name": full_name,
            "phone": phone,
            "address_line_1": address_line_1,
            "address_line_2": address_line_2,
            "city": city,
            "state": state,
            "postal_code": postal_code,
            "country": country,
            "is_default": is_default,
        })

        # Only letters (upper/lower), spaces, hyphens allowed
        name_pattern = re.compile(r"^[A-Za-z\s\-]+$")

        if not full_name:
            error["full_name"] = "Full name is required."
        elif not name_pattern.match(full_name):
            error["full_name"] = "Full name cannot have special characters or digits."
        if not phone:
            error["phone"] = "Phone is required."
        elif len(phone) != 10 or not phone.isdigit():
            error["phone"] = "Enter a valid 10-digit phone number."
        if not address_line_1:
            error["address_line_1"] = "Address Line 1 is required."
        if not city:
            error["city"] = "City is required."
        elif not name_pattern.match(city):
            error["city"] = "City cannot have special characters or digits."
        if not state:
            error["state"] = "State is required."
        elif not name_pattern.match(state):
            error["state"] = "State cannot have special characters or digits."
        if not postal_code:
            error["postal_code"] = "Postal code is required."
        elif len(postal_code) != 6 or not postal_code.isdigit():
            error["postal_code"] = "Enter a valid 6-digit postal code."
        if not country:
            error["country"] = "Country is required."
        elif not name_pattern.match(country):
            error["country"] = "Country cannot have special characters or digits."

        if not error:
            address = Address.objects.create(
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
            return render(request, "user/address/address_form.html", {"error": error, "form_data": form_data})

    return render(request, "user/address/address_form.html", {"form_data": form_data})
 

import re

@login_required(login_url='login')
@never_cache
def edit_address(request, pk):
    address = get_object_or_404(Address, pk=pk, user=request.user)
    error = {}

    form_data = {
        "full_name": address.full_name,
        "phone": address.phone,
        "address_line_1": address.address_line_1,
        "address_line_2": address.address_line_2,
        "city": address.city,
        "state": address.state,
        "postal_code": address.postal_code,
        "country": address.country,
        "is_default": address.is_default,
    }

    if request.method == "POST":
        full_name = request.POST.get("full_name", "").strip()
        phone = request.POST.get("phone", "").strip()
        address_line_1 = request.POST.get("address_line_1", "").strip()
        address_line_2 = request.POST.get("address_line_2", "").strip()
        city = request.POST.get("city", "").strip()
        state = request.POST.get("state", "").strip()
        postal_code = request.POST.get("postal_code", "").strip()
        country = request.POST.get("country", "India").strip()
        is_default = bool(request.POST.get("is_default"))

        # Update form_data from POST to persist inputs
        form_data.update({
            "full_name": full_name,
            "phone": phone,
            "address_line_1": address_line_1,
            "address_line_2": address_line_2,
            "city": city,
            "state": state,
            "postal_code": postal_code,
            "country": country,
            "is_default": is_default,
        })

        name_pattern = re.compile(r"^[A-Za-z\s\-]+$")

        if not full_name:
            error["full_name"] = "Full name is required."
        elif not name_pattern.match(full_name):
            error["full_name"] = "Full name cannot have special characters or digits."
        if not phone:
            error["phone"] = "Phone is required."
        elif len(phone) != 10 or not phone.isdigit():
            error["phone"] = "Enter a valid 10-digit phone number."
        if not address_line_1:
            error["address_line_1"] = "Address Line 1 is required."
        if not city:
            error["city"] = "City is required."
        elif not name_pattern.match(city):
            error["city"] = "City cannot have special characters or digits."
        if not state:
            error["state"] = "State is required."
        elif not name_pattern.match(state):
            error["state"] = "State cannot have special characters or digits."
        if not postal_code:
            error["postal_code"] = "Postal code is required."
        elif len(postal_code) != 6 or not postal_code.isdigit():
            error["postal_code"] = "Enter a valid 6-digit postal code."
        if not country:
            error["country"] = "Country is required."
        elif not name_pattern.match(country):
            error["country"] = "Country cannot have special characters or digits."

        if not error:
            # No errors - update and save
            address.full_name = full_name
            address.phone = phone
            address.address_line_1 = address_line_1
            address.address_line_2 = address_line_2
            address.city = city
            address.state = state
            address.postal_code = postal_code
            address.country = country
            address.is_default = is_default
            address.save()
            
            next_url = request.POST.get("next") or request.GET.get("next")
            if next_url:
                return redirect(next_url)
            return redirect("address_list")

        # If errors, render form with errors and inputs
        return render(request, "user/address/address_form.html", {
            "error": error,
            "form_data": form_data,
            "editing": True,
        })

    # Initial GET, render form with existing values
    return render(request, "user/address/address_form.html", {
        "form_data": form_data,
        "editing": True,
    })


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

