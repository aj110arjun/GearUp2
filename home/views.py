from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.views.decorators.cache import never_cache
from django.views.decorators.cache import cache_control
from django.contrib.admin.views.decorators import staff_member_required
from products.models import ProductVariant, Product
from django.db.models import OuterRef, Subquery



@never_cache
@login_required(login_url='login')
@cache_control(no_cache=True, must_revalidate=True, no_store=True)
def home(request):
    if request.user.is_staff:
        return redirect('login')
    if not request.user.is_authenticated:
        return redirect('login')
    subquery = ProductVariant.objects.filter(product=OuterRef('pk')).order_by('id')
    products = Product.objects.annotate(first_variant_id=Subquery(subquery.values('id')[:1]))[:8]
    variants = ProductVariant.objects.filter(id__in=[p.first_variant_id for p in products if p.first_variant_id])

    
    return render(request, 'user/index.html', {'products': variants})



# Admin Views

@staff_member_required(login_url='admin_login')
def dashboard(request):
    return render(request, 'custom_admin/dashboard.html')