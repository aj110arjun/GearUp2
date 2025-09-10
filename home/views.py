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
from reportlab.platypus import Table, TableStyle, Paragraph
from django.utils import timezone
from reportlab.lib.styles import getSampleStyleSheet



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

    # Order Stats
    total_orders = Order.objects.count()
    completed_orders = Order.objects.filter(payment_status="Paid").count()
    pending_orders = OrderItem.objects.filter(status="pending").count()
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

    context = {
        "total_orders": total_orders,
        "completed_orders": completed_orders,
        "pending_orders": pending_orders,
        "total_sales": total_sales,
        "top_products": top_products,
        "top_categories": top_categories,
        "top_brands": top_brands,
        "daily_sales": daily_sales,
        # "recent_activity": recent_activity
    }
    return render(request, 'custom_admin/dashboard.html', context)

@staff_member_required(login_url='admin_login')
def download_sales_report_pdf(request):
    # Create HttpResponse with PDF headers
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = 'attachment; filename="sales_report.pdf"'

    # Setup PDF canvas and page size
    pdf = canvas.Canvas(response, pagesize=A4)
    width, height = A4

    # Title styling and positioning
    pdf.setTitle("Sales Report")
    pdf.setFont("Helvetica-Bold", 20)
    pdf.drawCentredString(width / 2, height - 60, "Sales Report (Last 7 Days)")

    # Description or generated date
    pdf.setFont("Helvetica", 10)
    pdf.drawCentredString(width / 2, height - 80, f"Generated on: {date.today().strftime('%Y-%m-%d')}")

    # Prepare data for table with header
    table_data = [['Date', 'Total Sales (Rs.)', 'Orders Count', 'Top 3 Products (Quantity)']]

    styles = getSampleStyleSheet()
    wrap_style = styles["BodyText"]
    wrap_style.fontSize = 8
    wrap_style.leading = 10

    today = date.today()

    for i in range(6, -1, -1):
        current_day = today - timedelta(days=i)
        daily_orders = Order.objects.filter(payment_status='Pending', created_at__date=current_day)
        total_sales = daily_orders.aggregate(total=Sum('total_price'))['total'] or 0
        orders_count = daily_orders.count()

        top_products_qs = (
            OrderItem.objects.filter(order__in=daily_orders)
            .values('variant__product__name')
            .annotate(quantity_sold=Sum('quantity'))
            .order_by('-quantity_sold')[:3]
        )

        # Format top products as a Paragraph for word wrap
        product_lines = []
        for p in top_products_qs:
            product_lines.append(f"{p['variant__product__name']} ({p['quantity_sold']})")
        top_products_para = Paragraph('<br />'.join(product_lines) if product_lines else 'N/A', wrap_style)

        # Append each row; for Paragraph cell use later
        table_data.append([current_day.strftime('%Y-%m-%d'), f"Rs.{total_sales:,}", orders_count, top_products_para])

    # Create table with column widths
    col_widths = [80, 100, 80, 220]
    table = Table(table_data, colWidths=col_widths)

    # Define Table Style for headers and rows
    table_style = TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#007bff')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 12),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 10),
        ('TOPPADDING', (0, 0), (-1, 0), 10),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('VALIGN', (0, 1), (-1, -1), 'MIDDLE'),
        ('FONTSIZE', (0, 1), (-1, -1), 10),
        ('LEFTPADDING', (3, 1), (3, -1), 6),  # Padding in top products column
    ])
    table.setStyle(table_style)

    # Calculate Y position to draw the table (start below title)
    available_height = height - 120
    table_width, table_height = table.wrapOn(pdf, width - 80, available_height)
    x_start = 40
    y_start = available_height - table_height

    table.drawOn(pdf, x_start, y_start)

    # Finalize PDF
    pdf.showPage()
    pdf.save()

    return response