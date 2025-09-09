from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.views.decorators.cache import never_cache
from django.views.decorators.cache import cache_control
from django.contrib.admin.views.decorators import staff_member_required
from products.models import ProductVariant, Product
from django.db.models import OuterRef, Subquery, Sum, F, Count
from orders.models import Order, OrderItem
from datetime import date, timedelta
from django.http import HttpResponse
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib import colors
from reportlab.platypus import Table, TableStyle
from django.utils import timezone



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

@staff_member_required(login_url='admin_login')
@never_cache
def sales_chart_data(request):
    filter_type = request.GET.get('filter', 'daily')
    today = timezone.now().date()

    if filter_type == 'yearly':
        # Aggregate total sales per year for all years in DB
        qs = Order.objects.filter(payment_status="Paid").annotate(
            year=F('created_at__year')
        ).values('year').annotate(
            total=Sum('total_price')
        ).order_by('year')

        labels = [str(row['year']) for row in qs]
        sales = [float(row['total'] or 0) for row in qs]

    elif filter_type == 'monthly':
        # Aggregate total sales per month for the current year
        qs = Order.objects.filter(payment_status="Paid", created_at__year=today.year).annotate(
            month=F('created_at__month')
        ).values('month').annotate(
            total=Sum('total_price')
        ).order_by('month')

        labels = [f"{month_label(row['month'])}" for row in qs]
        sales = [float(row['total'] or 0) for row in qs]

    else:  # daily by default, last 7 days
        start_date = today - timedelta(days=6)
        qs = Order.objects.filter(payment_status="Paid", created_at__date__range=(start_date, today)).annotate(
            date=F('created_at__date')
        ).values('date').annotate(
            total=Sum('total_price')
        ).order_by('date')

        labels = [row['date'].strftime("%b %d") for row in qs]
        sales = [float(row['total'] or 0) for row in qs]

    return JsonResponse({'labels': labels, 'sales': sales})

def month_label(month_number):
    import calendar
    # Converts month number to short name like Jan, Feb...
    return calendar.month_abbr[month_number]

# Admin Views
@never_cache
@staff_member_required(login_url='admin_login')
def dashboard(request):
    if not request.user.is_staff or not request.user.is_authenticated:
        return redirect('admin_login')
    # daily_sales = [
    #     {"date": "Sep 03", "sales": 1500},
    #     {"date": "Sep 04", "sales": 1700},
    #     {"date": "Sep 05", "sales": 1800},
    #     {"date": "Sep 06", "sales": 1200},
    #     {"date": "Sep 07", "sales": 2200},
    #     {"date": "Sep 08", "sales": 2000},
    #     {"date": "Sep 09", "sales": 2500},
    # ]

    # Order Stats
    total_orders = Order.objects.count()
    completed_orders = Order.objects.filter(payment_status="Paid").count()
    pending_orders = Order.objects.filter(payment_status="Pending").count()
    total_sales_decimal = Order.objects.filter(payment_status="Paid") \
        .aggregate(total=Sum("total_price"))["total"] or 0
    total_sales = int(total_sales_decimal)

    # Top 10 Products
    top_products = (
        OrderItem.objects.values("variant__product__name")
        .annotate(quantity_sold=Sum("quantity"))
        .order_by("-quantity_sold")[:10]
    )

    # Top 10 Categories
    top_categories = (
        OrderItem.objects.values("variant__product__category__name")
        .annotate(quantity_sold=Sum("quantity"))
        .order_by("-quantity_sold")[:10]
    )

    # Top 10 Brands
    top_brands = (
    OrderItem.objects.values("variant__product__brand")
    .annotate(quantity_sold=Sum("quantity"))
    .order_by("-quantity_sold")[:10]
    )

    # Last 7 Days Sales
    today = date.today()
    last_7_days = [today - timedelta(days=i) for i in range(6, -1, -1)]
    daily_sales = []
    for day in last_7_days:
        day_sales = Order.objects.filter(
            payment_status="Paid", created_at__date=day
        ).aggregate(total=Sum("total_price"))["total"] or 0
        daily_sales.append({"date": day.strftime("%b %d"), "sales": float(day_sales)})

    # Recent Activity (customize as needed)
    recent_activity = [
        "Order #1022 placed",
        "Order #1021 marked as completed",
        "Product 'Rucksack Pro' reached top seller"
    ]

    context = {
        "total_orders": total_orders,
        "completed_orders": completed_orders,
        "pending_orders": pending_orders,
        "total_sales": total_sales,
        "top_products": top_products,
        "top_categories": top_categories,
        "top_brands": top_brands,
        "daily_sales": daily_sales,
        "recent_activity": recent_activity
    }
    return render(request, 'custom_admin/dashboard.html', context)

@staff_member_required(login_url='admin_login')
def download_sales_report_pdf(request):
    # Create the HttpResponse object
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = 'attachment; filename="sales_report.pdf"'

    # Create the PDF object, using A4 page size
    pdf = canvas.Canvas(response, pagesize=A4)
    width, height = A4
    pdf.setTitle("Sales Report")

    # Title
    pdf.setFont("Helvetica-Bold", 16)
    pdf.drawCentredString(width / 2, height - 50, "Sales Report (Last 7 Days)")

    # Prepare table data
    table_data = [['Date', 'Total Sales (Rs.)', 'Orders Count', 'Top Products']]

    today = date.today()
    for i in range(6, -1, -1):
        day = today - timedelta(days=i)
        orders = Order.objects.filter(payment_status='Pending', created_at__date=day)
        total_sales = orders.aggregate(total=Sum('total_price'))['total'] or 0
        orders_count = orders.count()

        # Top 3 products sold
        top_products_qs = (
            OrderItem.objects.filter(order__in=orders)
            .values('variant__product__name')
            .annotate(quantity_sold=Sum('quantity'))
            .order_by('-quantity_sold')[:3]
        )
        top_products_str = ', '.join([f"{p['variant__product__name']}({p['quantity_sold']})" for p in top_products_qs])

        table_data.append([day.strftime('%Y-%m-%d'), str(total_sales), str(orders_count), top_products_str])

    # Create Table
    table = Table(table_data, colWidths=[100, 100, 100, 200])
    style = TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.lightgrey),
        ('TEXTCOLOR', (0,0), (-1,0), colors.black),
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('GRID', (0,0), (-1,-1), 0.5, colors.black),
    ])
    table.setStyle(style)

    # Calculate table position
    table_width, table_height = table.wrapOn(pdf, width, height)
    table.drawOn(pdf, 40, height - 100 - table_height)

    pdf.showPage()
    pdf.save()
    return response