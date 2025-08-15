from django.shortcuts import render
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required

from django.db.models import Q, Min, Max, Sum
from .models import Product, ProductVariant, Category


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

from django.db.models import Q, Min, Sum

def admin_product_list(request):
    products = Product.objects.select_related('category').annotate(
    min_variant_price=Min('variants__price'),
    total_stock=Sum('variants__stock')
)
    categories = Category.objects.all()

    # Capture filters from query params
    filters = {
        'category': request.GET.get('category', ''),
        'in_stock': request.GET.get('in_stock', ''),
        'is_active': request.GET.get('is_active', ''),
        'search': request.GET.get('q', ''),
        'sort': request.GET.get('sort', '')
    }

    # Annotate price and stock
    products = products.annotate(
        min_variant_price=Min('variants__price'),
        total_stock=Sum('variants__stock')
    )

    # Category filter
    if filters['category']:
        products = products.filter(category_id=filters['category'])

    # Stock filter
    if filters['in_stock'] == 'true':
        products = products.filter(total_stock__gt=0)
    elif filters['in_stock'] == 'false':
        products = products.filter(Q(total_stock__lte=0) | Q(total_stock__isnull=True))

    # Active/Inactive filter
    if filters['is_active'] == 'true':
        products = products.filter(is_active=True)
    elif filters['is_active'] == 'false':
        products = products.filter(is_active=False)

    # Search filter
    if filters['search']:
        products = products.filter(
            Q(name__icontains=filters['search']) |
            Q(description__icontains=filters['search']) |
            Q(brand__icontains=filters['search']) |
            Q(category__name__icontains=filters['search'])
        )

    # Sorting
    if filters['sort'] == 'name':
        products = products.order_by('name')
    elif filters['sort'] == 'price_asc':
        products = products.order_by('min_variant_price')
    elif filters['sort'] == 'price_desc':
        products = products.order_by('-min_variant_price')
    elif filters['sort'] == 'stock_asc':
        products = products.order_by('total_stock')
    elif filters['sort'] == 'stock_desc':
        products = products.order_by('-total_stock')
    else:
        products = products.order_by('-id')  # latest first

    context = {
        'products': products,
        'categories': categories,
        'filters': filters
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

# @login_required(login_url="admin_login")
def admin_product_detail(request, pk):
    product = get_object_or_404(Product, pk=pk)
    variants = product.variants.all()  # assuming related_name="variants" in ProductVariant model
    # additional_images = product.images.all()  # assuming related_name="images" in ProductImage model

    return render(request, "custom_admin/products/product_detail.html", {
        "product": product,
        "variants": variants,
        # "additional_images": additional_images
    })

def admin_product_edit(request, pk):
    product = get_object_or_404(Product, pk=pk)
    categories = Category.objects.all() 

    if request.method == "POST":
        # --- Update main product ---
        product.name = request.POST.get('name')
        product.brand = request.POST.get('brand')
        product.description = request.POST.get('description')
        product.category_id = request.POST.get('category')
        product.is_active = request.POST.get('is_active') == 'on'
        if request.FILES.get('image'):
            product.image = request.FILES['image']
        product.save()

        # --- Update additional images ---
        # for img_id in request.POST.getlist('image_id'):
        #     img = ProductImage.objects.get(id=img_id)
        #     if f'delete_image_{img.id}' in request.POST:
        #         img.delete()

        # Add new images
        # for file in request.FILES.getlist('new_images'):
        #     ProductImage.objects.create(product=product, image=file)

        # --- Update variants ---
        for var_id in request.POST.getlist('variant_id'):
            variant = ProductVariant.objects.get(id=var_id)
            if f'delete_variant_{variant.id}' in request.POST:
                variant.delete()
            else:
                variant.color = request.POST.get(f'color_{variant.id}')
                variant.size = request.POST.get(f'size_{variant.id}')
                variant.price = request.POST.get(f'price_{variant.id}')
                variant.stock = request.POST.get(f'stock_{variant.id}')
                variant.save()

        # Add new variant
        new_color = request.POST.get('new_color')
        new_size = request.POST.get('new_size')
        new_price = request.POST.get('new_price')
        new_stock = request.POST.get('new_stock')
        if new_color and new_size:
            ProductVariant.objects.create(
                product=product,
                color=new_color,
                size=new_size,
                price=new_price or 0,
                stock=new_stock or 0
            )

        return redirect('admin_product_detail', pk=product.pk)

    # GET request — render page
    # additional_images = product.productimage_set.all()
    variants = product.variants.all()

    return render(request, 'custom_admin/products/product_edit.html', {
        'product': product,
        # 'additional_images': additional_images,
        'categories': categories,
        'variants': variants
    })
    
def toggle_product_status(request, pk):
    product = get_object_or_404(Product, pk=pk)
    
    # Toggle active status
    product.is_active = not product.is_active
    product.save()
    return redirect('admin_product_detail', pk=pk)



