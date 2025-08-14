from django.shortcuts import render
from django.shortcuts import render, redirect, get_object_or_404

from django.db.models import Q, Min, Max, Sum
from .models import Product, Category


def product_list(request):
    products = Product.objects.filter(is_active=True)
    categories = Category.objects.all()

    # Capture filters
    filters = {
        'category': request.GET.get('category', ''),
        'min_price': request.GET.get('min_price', ''),
        'max_price': request.GET.get('max_price', ''),
        'in_stock': request.GET.get('in_stock', ''),
        'search': request.GET.get('q', ''),  # Match form input name
        'sort': request.GET.get('sort', '')
    }

    # Annotate for price & stock
    products = products.annotate(
        min_variant_price=Min('variants__price'),
        total_stock=Sum('variants__stock')
    )

    # Category filter
    if filters['category']:
        products = products.filter(category_id=filters['category'])

    # Price filters
    if filters['min_price']:
        products = products.filter(min_variant_price__gte=filters['min_price'])
    if filters['max_price']:
        products = products.filter(min_variant_price__lte=filters['max_price'])

    # Stock filter
    if filters['in_stock'] == 'true':
        products = products.filter(total_stock__gt=0)
    elif filters['in_stock'] == 'false':
        products = products.filter(Q(total_stock__lte=0) | Q(total_stock__isnull=True))

    # Search filter — if nothing matches, will return an empty queryset
    if filters['search']:
        products = products.filter(
            Q(name__icontains=filters['search']) |
            Q(description__icontains=filters['search']) |
            Q(category__name__icontains=filters['search'])
        )

    # Sorting
    if filters['sort'] == 'name':
        products = products.order_by('name')
    elif filters['sort'] == 'price_asc':
        products = products.order_by('min_variant_price')
    elif filters['sort'] == 'price_desc':
        products = products.order_by('-min_variant_price')

    context = {
        'products': products,
        'categories': categories,
        'filters': filters
    }
    return render(request, 'user/products/product_list.html', context)



# Admin View

def admin_product_list(request):
    products = Product.objects.all()
    context={
        'products': products
    }
    return render(request, 'custom_admin/products/product_list.html', context)


def admin_product_add(request):
    categories = Category.objects.all()

    if request.method == 'POST':
        name = request.POST.get('name')
        description = request.POST.get('description', '')
        category_id = request.POST.get('category')
        brand = request.POST.get('brand', '')
        image = request.FILES.get('image')
        is_active = request.POST.get('is_active') == 'on'

        category = Category.objects.get(id=category_id) if category_id else None

        Product.objects.create(
            name=name,
            description=description,
            category=category,
            brand=brand,
            image=image,
            is_active=is_active
        )

        return redirect('admin_product_list')

    return render(request, 'custom_admin/products/product_form.html', {
        'categories': categories
    })

def category_list(request):
    categories = Category.objects.all()
    return render(request, 'custom_admin/category/category_list.html', {'categories': categories})

def category_add(request):
    if request.method == 'POST':
        name = request.POST.get('name')
        description = request.POST.get('description', '')
        parent_id = request.POST.get('parent')
        parent = Category.objects.get(id=parent_id) if parent_id else None
        Category.objects.create(name=name, description=description, parent=parent)
        return redirect('category_list')

    categories = Category.objects.filter(parent__isnull=True)
    return render(request, 'custom_admin/category/category_form.html', {'categories': categories})

def category_edit(request, pk):
    category = get_object_or_404(Category, pk=pk)
    if request.method == 'POST':
        category.name = request.POST.get('name')
        category.description = request.POST.get('description', '')
        parent_id = request.POST.get('parent')
        category.parent = Category.objects.get(id=parent_id) if parent_id else None
        category.save()
        return redirect('category_list')

    categories = Category.objects.filter(parent__isnull=True).exclude(id=pk)
    return render(request, 'custom_admin/category/category_form.html', {
        'category': category,
        'categories': categories
    })
    
def category_delete(request, pk):
    category = get_object_or_404(Category, pk=pk)
    category.delete()
    return redirect('category_list')

