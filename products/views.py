import re

from django.contrib import messages
from django.shortcuts import render
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.views.decorators.cache import never_cache
from django.contrib.admin.views.decorators import staff_member_required
from django.core.paginator import Paginator
from django.db.models import Q, Min, Max, Sum
from django.urls import reverse
from django.http import JsonResponse
from django.core.files.base import ContentFile
import base64

from .models import Product, ProductVariant, Category, ProductImage
from wishlist.models import Wishlist
from cart.models import CartItem


@login_required(login_url='login')
@never_cache
def product_list(request):
    products = Product.objects.filter(is_active=True).prefetch_related("variants")
    categories = Category.objects.all()

    filters = {
        'category': request.GET.get('category', ''),
        'search': request.GET.get('q', ''),
        'sort': request.GET.get('sort', '')
    }

    if filters['category']:
        products = products.filter(category_id=filters['category'])

    if filters['search']:
        products = products.filter(
            Q(name__icontains=filters['search']) |
            Q(description__icontains=filters['search']) |
            Q(category__name__icontains=filters['search'])
        )

    # Sorting
    if filters['sort'] == 'name':
        products = products.order_by('name')
    elif filters['sort'] == 'name2':
        products = products.order_by('-name')
    elif filters['sort'] == 'price_asc':
        products = products.annotate(min_price=Min('variants__price')).order_by('min_price')
    elif filters['sort'] == 'price_desc':
        products = products.annotate(min_price=Min('variants__price')).order_by('-min_price')

    # Pagination
    paginator = Paginator(products, 8)
    page_number = request.GET.get('page')
    products = paginator.get_page(page_number)

    # ✅ Attach best offer objects
    for p in products:
        p.best_offer = p.get_best_offer_obj()
    
    breadcrumbs = [
        ("Home", reverse("home")),
        ("Products", None),
    ]

    wishlist_ids = Wishlist.objects.filter(user=request.user).values_list('product_id', flat=True)
    cart_variant_ids = list(CartItem.objects.filter(user=request.user).values_list('variant_id', flat=True)) if request.user.is_authenticated else []

    context = {
        'products': products,
        'categories': categories,
        'filters': filters,
        'wishlist_ids': wishlist_ids,
        'cart_variant_ids': cart_variant_ids,
        'breadcrumbs': breadcrumbs,
    }

    return render(request, 'user/products/product_list.html', context)





@login_required(login_url='login')
@never_cache
def product_detail(request, product_id):
    product = get_object_or_404(Product, product_id=product_id, is_active=True)
    variants = product.variants.all()
    additional_images = product.images.all()
    in_wishlist = False
    if request.user.is_authenticated:
        in_wishlist = Wishlist.objects.filter(user=request.user, product=product).exists()
    
    breadcrumbs = [
        ("Home", reverse("home")),
        ("Products", reverse("product_list")),
        (product.name, None),
    ]
        
    cart_items = CartItem.objects.filter(user=request.user).values_list("variant_id", flat=True)
    return render(request, "user/products/product_detail.html", {
        "product": product,
        "variants": variants,
        "in_wishlist": in_wishlist,
        "cart_items": cart_items,
        "additional_images": additional_images,
        "breadcrumbs": breadcrumbs,
    })




# Admin View

@staff_member_required(login_url='admin_login')
@never_cache
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

    paginator = Paginator(products, 6)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    context = {
        'products': page_obj,   # pass paginated products
        'categories': categories,
        'filters': filters,
    }
    return render(request, 'custom_admin/products/product_list.html', context)


@staff_member_required(login_url='admin_login')
@never_cache
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
        if not re.match(r'^[A-Za-z\s]+$', name):
            errors['name'] = "Product name must contain only letters and spaces"

        elif len(name) < 3:
            errors['name'] = "Product name must be at least 3 characters."
        elif not re.match(r'^[A-Za-z0-9 ]+$', name):
            errors['name'] = "Product name can only contain letters, numbers, and spaces."
        elif Product.objects.filter(name__iexact=name).exists():
            errors['name'] = "A product with this name already exists."

        if not brand:
            errors['brand'] = "Brand is required."
        if not re.match(r'^[A-Za-z\s]+$', brand):
            errors['brand'] = "Brand must contain only letters and spaces"
        if len(brand)<3:
            errors['brand'] = "Brand must contain 3 characters"

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

        # --- If validation fails ---
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
@never_cache
def category_list(request):
    categories = Category.objects.all().order_by('name')  # optional sorting

    # ✅ Pagination (6 categories per page, you can change number)
    paginator = Paginator(categories, 6)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    return render(
        request,
        'custom_admin/category/category_list.html',
        {'categories': page_obj}
    )

@staff_member_required(login_url='admin_login')
@never_cache
def category_add(request):
    errors={}
    if request.method == 'POST':
        name = request.POST.get('name')
        description = request.POST.get('description', '')
        parent_id = request.POST.get('parent')
        parent = Category.objects.get(id=parent_id) if parent_id else None
        
        if Category.objects.filter(name__iexact = name):
            errors['name']='Category name already exists'
        elif not name:
            errors['name'] = 'Category name cannot be empty'
        if not errors:
            Category.objects.create(name=name, description=description, parent=parent)
            return redirect('category_list')
        

    categories = Category.objects.filter(parent__isnull=True)
    return render(request, 'custom_admin/category/category_form.html', {'categories': categories, 'errors':errors})

@staff_member_required(login_url='admin_login')
@never_cache
def category_edit(request, id):
    errors = {}
    category = get_object_or_404(Category, id=id)

    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        description = request.POST.get('description', '').strip()
        parent_id = request.POST.get('parent')

        # Check if name already exists (excluding current one)
        if Category.objects.filter(name__iexact=name).exclude(id=id).exists():
            errors['name'] = 'Category name already exists'
        elif not name:
            errors['name'] = 'Category name cannot be empty'
            

        if not errors:
            category.name = name
            category.description = description
            category.parent = Category.objects.get(id=parent_id) if parent_id else None
            category.save()
            return redirect('category_list')

    categories = Category.objects.filter(parent__isnull=True).exclude(id=id)
    return render(request, 'custom_admin/category/category_form.html', {
        'category': category,
        'categories': categories,
        'errors': errors,
    })


@staff_member_required(login_url='admin_login')
@never_cache
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
@never_cache
def admin_product_edit(request, product_id):
    product = get_object_or_404(Product, product_id=product_id)
    categories = Category.objects.all()
    errors = {}
    
    if request.method == "POST":
        # --- Update main product only ---
        product.name = request.POST.get('name', '').strip()
        product.brand = request.POST.get('brand', '').strip()
        product.description = request.POST.get('description', '').strip()
        product.category_id = request.POST.get('category')
        product.is_active = request.POST.get('is_active') == 'on'
        if request.FILES.get('image'):
            product.image = request.FILES['image']
        product.save()

        error_flag = False
        if not product.name:
            errors['name'] = 'Product name is required.'
            error_flag = True
        if not re.match(r'^[A-Za-z\s]+$', product.name):
            errors['name'] = "Product name must contain only letters and spaces"
            error_flag = True
        if len(product.name) < 3:
            errors['name'] = "Product name must atleast 3 characters"
            error_flag = True
        if not product.brand:
            errors['brand'] = 'Brand is required.'
            error_flag = True
        if not product.category_id:
            errors['category'] = 'Category must be selected.'
            error_flag = True
        if not product.description:
            errors['description'] = 'Description is required.'
            error_flag = True

        if error_flag:
            # Still send existing variants & images for display purposes
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
    additional_images = product.images.all()  # For display only
    variants = product.variants.all()          # For display only
    return render(request, 'custom_admin/products/product_edit.html', {
        'product': product,
        'additional_images': additional_images,
        'categories': categories,
        'variants': variants,
        'errors': {}
    })



@staff_member_required(login_url='admin_login')
def admin_variant_add(request, product_id):
    product = get_object_or_404(Product, pk=product_id)
    errors = {}
    if request.method == "POST":
        color = request.POST.get('color', '').strip()
        size = request.POST.get('size', '').strip()
        price = request.POST.get('price')
        stock = request.POST.get('stock')
        error_flag = False

        if not color:
            errors['color'] = "Color is required."
            error_flag = True
        if not size:
            errors['size'] = "Size is required."
            error_flag = True
        try:
            price = float(price)
            stock = int(stock)
        except (ValueError, TypeError):
            errors['price'] = "Invalid price."
            errors['stock'] = "Invalid stock."
            error_flag = True
        else:
            if price < 0:
                errors['price'] = "Price must be positive."
                error_flag = True
            if stock < 0:
                errors['stock'] = "Stock must be positive."
                error_flag = True

        if not error_flag:
            ProductVariant.objects.create(
                product=product,
                color=color,
                size=size,
                price=price,
                stock=stock
            )
            return redirect('admin_product_edit', product_id=product.product_id)

    return render(request, 'custom_admin/products/variant_add.html', {
        'product': product,
        'errors': errors
    })

@staff_member_required(login_url='admin_login')
def admin_variant_edit(request, variant_id):
    variant = get_object_or_404(ProductVariant, pk=variant_id)
    errors = {}

    if request.method == "POST":
        color = request.POST.get('color', '').strip()
        size = request.POST.get('size', '').strip()
        price = request.POST.get('price')
        stock = request.POST.get('stock')
        error_flag = False

        if not color:
            errors['color'] = "Color is required."
            error_flag = True
        if not size:
            errors['size'] = "Size is required."
            error_flag = True
        try:
            price = float(price)
            stock = int(stock)
        except (ValueError, TypeError):
            errors['price'] = "Invalid price."
            errors['stock'] = "Invalid stock."
            error_flag = True
        else:
            if price < 0:
                errors['price'] = "Price must be positive."
                error_flag = True
            if stock < 0:
                errors['stock'] = "Stock must be positive."
                error_flag = True

        if not error_flag:
            variant.color = color
            variant.size = size
            variant.price = price
            variant.stock = stock
            variant.save()
            return redirect('admin_product_edit', product_id=variant.product.product_id)

    return render(request, 'custom_admin/products/variant_edit.html', {
        'variant': variant,
        'product': variant.product,
        'errors': errors
    })

@staff_member_required(login_url='admin_login')
def admin_variant_delete(request, variant_id):
    variant = get_object_or_404(ProductVariant, pk=variant_id)
    product_id = variant.product.product_id
    if request.method == "POST":
        variant.delete()
        return redirect('admin_product_edit', product_id=product_id)
    return render(request, 'custom_admin/products/variant_confirm_delete.html', {
        'variant': variant,
        'product': variant.product
    })


@staff_member_required(login_url='admin_login')
def admin_image_add(request, product_id):
    product = get_object_or_404(Product, pk=product_id)
    errors = {}

    if request.method == "POST":
        cropped_data = request.POST.get('cropped_image_data')
        if cropped_data:
            format, imgstr = cropped_data.split(';base64,')  
            ext = format.split('/')[-1]  
            data = ContentFile(base64.b64decode(imgstr), name='cropped.' + ext)
            ProductImage.objects.create(product=product, image=data)
            return redirect('admin_product_edit', product_id=product.product_id)
        images = request.FILES.getlist('images')
        if not images:
            errors['images'] = "Please upload at least one image."
        else:
            for img in images:
                ProductImage.objects.create(product=product, image=img)
            return redirect('admin_product_edit', product_id=product.product_id)

    return render(request, 'custom_admin/products/image_add.html', {
        'product': product,
        'errors': errors
    })





@staff_member_required(login_url='admin_login')
@never_cache 
def toggle_product_status(request, product_id):
    product = get_object_or_404(Product, product_id=product_id)
    
    # Toggle active status
    product.is_active = not product.is_active
    product.save()
    return redirect('admin_product_detail', product_id=product_id)



