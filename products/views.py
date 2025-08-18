from django.contrib import messages
from django.shortcuts import render
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.admin.views.decorators import staff_member_required
from django.core.paginator import Paginator


from django.db.models import Q, Min, Max, Sum
from .models import Product, ProductVariant, Category, ProductImage
from wishlist.models import Wishlist
from cart.models import CartItem

@login_required(login_url='login')
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

    # Search filter
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

    # ✅ Pagination AFTER filters + sorting
    paginator = Paginator(products, 8)
    page_number = request.GET.get('page')
    products = paginator.get_page(page_number)

    context = {
        'products': products,
        'categories': categories,
        'filters': filters
    }
    return render(request, 'user/products/product_list.html', context)


@login_required(login_url='login')
def product_detail(request, product_id):
    product = get_object_or_404(Product, product_id=product_id, is_active=True)
    variants = product.variants.all()
    additional_images = product.images.all()
    in_wishlist = False
    if request.user.is_authenticated:
        in_wishlist = Wishlist.objects.filter(user=request.user, product=product).exists()
        
    cart_items = CartItem.objects.filter(user=request.user).values_list("variant_id", flat=True)
    return render(request, "user/products/product_detail.html", {
        "product": product,
        "variants": variants,
        "in_wishlist": in_wishlist,
        "cart_items": cart_items,
        "additional_images": additional_images,
    })




# Admin View

@staff_member_required(login_url='admin_login')
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


from django.contrib import messages

@staff_member_required(login_url='admin_login')
def admin_product_add(request):
    categories = Category.objects.all()
    errors = {}
    form_data = {}

    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        description = request.POST.get('description', '').strip()
        category_id = request.POST.get('category')
        brand = request.POST.get('brand', '').strip()
        image = request.FILES.get('image')
        is_active = request.POST.get('is_active') == 'on'

        # Save form data so we can repopulate
        form_data = {
            'name': name,
            'description': description,
            'brand': brand,
            'category': category_id,
            'is_active': is_active,
        }

        # --- Validation ---
        if not name:
            errors['name'] = "Product name is required."

        if not brand:
            errors['brand'] = "Brand is required."

        if not description:
            errors['description'] = "Description is required."

        if not category_id:
            errors['category'] = "Category is required."
            category = None
        else:
            try:
                category = Category.objects.get(id=category_id)
            except Category.DoesNotExist:
                errors['category'] = "Invalid category selected."
                category = None

        if not image:
            errors['image'] = "Product image is required."

        # --- If validation fails, reload form with errors ---
        if errors:
            return render(request, 'custom_admin/products/product_form.html', {
                'categories': categories,
                'errors': errors,
                'form_data': form_data
            })

        # --- Create product ---
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
        'categories': categories,
        'errors': errors,
        'form_data': form_data
    })


@staff_member_required(login_url='admin_login')
def category_list(request):
    categories = Category.objects.all()
    return render(request, 'custom_admin/category/category_list.html', {'categories': categories})

@staff_member_required(login_url='admin_login')
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

@staff_member_required(login_url='admin_login')
def category_edit(request, id):
    category = get_object_or_404(Category, id=id)
    if request.method == 'POST':
        category.name = request.POST.get('name')
        category.description = request.POST.get('description', '')
        parent_id = request.POST.get('parent')
        category.parent = Category.objects.get(id=parent_id) if parent_id else None
        category.save()
        return redirect('category_list')

    categories = Category.objects.filter(parent__isnull=True).exclude(id=id)
    return render(request, 'custom_admin/category/category_form.html', {
        'category': category,
        'categories': categories
    })

@staff_member_required(login_url='admin_login')
def category_delete(request, pk):
    category = get_object_or_404(Category, pk=pk)
    category.delete()
    return redirect('category_list')

@staff_member_required(login_url='admin_login')
def admin_product_detail(request, product_id):
    product = get_object_or_404(Product, product_id=product_id)
    variants = product.variants.all()  # assuming related_name="variants" in ProductVariant model
    # additional_images = product.images.all()  # assuming related_name="images" in ProductImage model

    return render(request, "custom_admin/products/product_detail.html", {
        "product": product,
        "variants": variants,
        # "additional_images": additional_images
    })


@staff_member_required(login_url='admin_login')
def admin_product_edit(request, product_id):
    product = get_object_or_404(Product, product_id=product_id)
    categories = Category.objects.all()
    errors = {}
    
    if request.method == "POST":
        # --- Update main product ---
        product.name = request.POST.get('name', '').strip()
        product.brand = request.POST.get('brand', '').strip()
        product.description = request.POST.get('description', '').strip()
        product.category_id = request.POST.get('category')
        product.is_active = request.POST.get('is_active') == 'on'
        if request.FILES.get('image'):
            product.image = request.FILES['image']
        product.save()

        error_flag = False

        # --- Update existing variants ---
        for var_id in request.POST.getlist('variant_id'):
            variant = ProductVariant.objects.get(id=var_id)

            if f'delete_variant_{variant.id}' in request.POST:
                variant.delete()
                continue

            color = request.POST.get(f'color_{variant.id}', '').strip()
            size = request.POST.get(f'size_{variant.id}', '').strip()
            price = request.POST.get(f'price_{variant.id}')
            stock = request.POST.get(f'stock_{variant.id}')

            # Required field validation
            if not color:
                errors[f'color'] = "Color is required."
                error_flag = True
            if not size:
                errors[f'size'] = "Size is required."
                error_flag = True

            # Price & stock validation
            try:
                price = float(price)
                stock = int(stock)
            except (ValueError, TypeError):
                errors[f'variant'] = "Invalid price or stock."
                error_flag = True
                continue

            if price < 0 or stock < 0:
                errors[f'variant'] = "Price and stock must be non-negative."
                error_flag = True
                continue

            # Only save if no field errors for this variant
            if not error_flag:
                variant.color = color
                variant.size = size
                variant.price = price
                variant.stock = stock
                variant.save()

        # --- Add new variant ---
        new_color = request.POST.get('new_color', '').strip()
        new_size = request.POST.get('new_size', '').strip()
        new_price = request.POST.get('new_price')
        new_stock = request.POST.get('new_stock')

        if new_color or new_size or new_price or new_stock:  # only if any field entered
            if not new_color:
                errors['new_color'] = "Color is required for new variant."
                error_flag = True
            if not new_size:
                errors['new_size'] = "Size is required for new variant."
                error_flag = True

            try:
                new_price = float(new_price or 0)
                new_stock = int(new_stock or 0)
            except (ValueError, TypeError):
                errors['new_variant'] = "Invalid price or stock for new variant."
                error_flag = True
            else:
                if new_price < 0 or new_stock < 0:
                    errors['new_variant'] = "Price and stock must be non-negative."
                    error_flag = True

            if not error_flag:
                ProductVariant.objects.create(
                    product=product,
                    color=new_color,
                    size=new_size,
                    price=new_price,
                    stock=new_stock
                )

        # --- Update images ---
        for img_id in request.POST.getlist('image_id'):
            if f'delete_image_{img_id}' in request.POST:
                ProductImage.objects.filter(id=img_id, product=product).delete()
        for file in request.FILES.getlist('new_images'):
            ProductImage.objects.create(product=product, image=file)

        if error_flag:
            additional_images = product.images.all()
            variants = product.variants.all()
            return render(request, 'custom_admin/products/product_edit.html', {
                'product': product,
                'additional_images': additional_images,
                'categories': categories,
                'variants': variants,
                'errors': errors
            })

        return redirect('admin_product_detail', product_id=product.product_id)

    # --- GET request ---
    additional_images = product.images.all()
    variants = product.variants.all()

    return render(request, 'custom_admin/products/product_edit.html', {
        'product': product,
        'additional_images': additional_images,
        'categories': categories,
        'variants': variants,
        'errors': {}
    })



@staff_member_required(login_url='admin_login')   
def toggle_product_status(request, product_id):
    product = get_object_or_404(Product, product_id=product_id)
    
    # Toggle active status
    product.is_active = not product.is_active
    product.save()
    return redirect('admin_product_detail', product_id=product_id)



