from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.views.decorators.cache import never_cache
from django.views.decorators.cache import cache_control
from django.contrib.admin.views.decorators import staff_member_required
from products.models import ProductVariant, Product
from django.db.models import OuterRef, Subquery, Sum, F, Count
from orders.models import Order
from datetime import date, timedelta
from django.http import HttpResponse
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib import colors
from reportlab.platypus import Table, TableStyle, Paragraph
from django.utils import timezone
from reportlab.lib.styles import getSampleStyleSheet
from django.db.models.functions import ExtractMonth, ExtractYear
from django.http import JsonResponse




@never_cache
@login_required(login_url='login')
@cache_control(no_cache=True, must_revalidate=True, no_store=True)
def home(request):
    if request.user.is_staff:
        return redirect('login')
    if not request.user.is_authenticated:
        return redirect('login')
    subquery = ProductVariant.objects.filter(product=OuterRef('pk')).order_by('id')
    products = Product.objects.filter(is_active = True).annotate(first_variant_id=Subquery(subquery.values('id')[:1]))[:8]
    variants = ProductVariant.objects.filter(id__in=[p.first_variant_id for p in products if p.first_variant_id])

    breadcrumbs = [
        ("Home", None)
    ]
    context = {
        'products': variants,
        'breadcrumbs': breadcrumbs,
    }

    
    return render(request, 'user/index.html', context)

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

    # Get filter from GET params; default to 'daily'
    selected_filter = request.GET.get('filter', 'daily')

    # Order Stats
    total_orders = Order.objects.count()
    completed_orders = Order.objects.filter(payment_status="Paid").count()
    pending_orders = Order.objects.filter(order_status="Pending").count()  # Uncommented
    total_sales_decimal = Order.objects.filter(payment_status="Paid") \
        .aggregate(total=Sum("total_price"))["total"] or 0
    total_sales = int(total_sales_decimal)

    # Top 10 Products (commented out as in your original)
    top_products = []  # Placeholder since you commented this out
    # top_products = (
    #     OrderItem.objects.values("variant__product__name")
    #     .annotate(quantity_sold=Sum("quantity"))
    #     .order_by("-quantity_sold")[:10]
    # )

    # Top 10 Categories (commented out as in your original)
    top_categories = []  # Placeholder
    # top_categories = (
    #     OrderItem.objects.values("variant__product__category__name")
    #     .annotate(quantity_sold=Sum("quantity"))
    #     .order_by("-quantity_sold")[:10]
    # )

    # Top 10 Brands (commented out as in your original)
    top_brands = []  # Placeholder
    # top_brands = (
    #     OrderItem.objects.values("variant__product__brand")
    #     .annotate(quantity_sold=Sum("quantity"))
    #     .order_by("-quantity_sold")[:10]
    # )

    today = date.today()
    sales_data = []

    if selected_filter == 'monthly':
        # Aggregate total sales per month for the current year
        sales_qs = (
            Order.objects.filter(payment_status="Paid", created_at__year=today.year)
            .annotate(month=ExtractMonth("created_at"))
            .values("month")
            .annotate(total=Sum("total_price"))
            .order_by("month")
        )
        
        # Prepare monthly sales data with month labels (Jan, Feb, etc.)
        monthly_sales = []
        month_names = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 
                       'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
        
        # Create a dictionary for easy lookup
        sales_dict = {item['month']: float(item['total']) for item in sales_qs}
        
        for i in range(1, 13):
            total = sales_dict.get(i, 0.0)
            monthly_sales.append({"date": month_names[i-1], "sales": total})

        sales_data = monthly_sales

    elif selected_filter == 'yearly':
        # Aggregate total sales per year for all available years
        sales_qs = (
            Order.objects.filter(payment_status="Paid")
            .annotate(year=ExtractYear("created_at"))
            .values("year")
            .annotate(total=Sum("total_price"))
            .order_by("year")
        )
        
        yearly_sales = []
        for item in sales_qs:
            yearly_sales.append({
                "date": str(item['year']), 
                "sales": float(item['total'])
            })

        sales_data = yearly_sales

    else:
        # Daily - last 7 days sales
        last_7_days = [today - timedelta(days=i) for i in range(6, -1, -1)]
        daily_sales = []
        
        for day in last_7_days:
            day_sales = Order.objects.filter(
                payment_status="Paid", 
                created_at__date=day
            ).aggregate(total=Sum("total_price"))["total"] or 0
            
            daily_sales.append({
                "date": day.strftime("%b %d"), 
                "sales": float(day_sales)
            })
        
        sales_data = daily_sales

    context = {
        "total_orders": total_orders,
        "completed_orders": completed_orders,
        "pending_orders": pending_orders,
        "total_sales": total_sales,
        "top_products": top_products,
        "top_categories": top_categories,
        "top_brands": top_brands,
        "daily_sales": sales_data,  # dynamic sales data by filter
        "selected_filter": selected_filter,
    }
    return render(request, 'custom_admin/dashboard.html', context)

@staff_member_required(login_url='admin_login')
@never_cache
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
    table_data = [['Date', 'Total Sales (Rs.)', 'Orders Count', 'Status Breakdown', 'Avg. Order Value']]

    styles = getSampleStyleSheet()
    wrap_style = styles["BodyText"]
    wrap_style.fontSize = 8
    wrap_style.leading = 10

    today = date.today()
    weekly_data = []

    for i in range(6, -1, -1):
        current_day = today - timedelta(days=i)
        daily_orders = Order.objects.filter(created_at__date=current_day)
        total_sales = daily_orders.aggregate(total=Sum('total_price'))['total'] or 0
        orders_count = daily_orders.count()
        
        # Calculate average order value
        avg_order_value = total_sales / orders_count if orders_count > 0 else 0

        # Get status breakdown
        paid_count = daily_orders.filter(payment_status='Paid').count()
        pending_count = daily_orders.filter(payment_status='Pending').count()
        status_info = f"Paid: {paid_count}\nPending: {pending_count}"
        status_para = Paragraph(status_info, wrap_style)

        # Append each row
        table_data.append([
            current_day.strftime('%Y-%m-%d'), 
            f"Rs.{total_sales:,.0f}", 
            orders_count, 
            status_para, 
            f"Rs.{avg_order_value:,.0f}" if orders_count > 0 else "Rs.0"
        ])
        
        weekly_data.append({
            'date': current_day,
            'total_sales': total_sales,
            'orders_count': orders_count,
            'paid_count': paid_count,
            'pending_count': pending_count
        })

    # Create table with column widths
    col_widths = [80, 90, 70, 80, 90]
    table = Table(table_data, colWidths=col_widths)

    # Define Table Style for headers and rows
    table_style = TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#007bff')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 9),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
        ('TOPPADDING', (0, 0), (-1, 0), 8),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('VALIGN', (0, 1), (-1, -1), 'MIDDLE'),
        ('FONTSIZE', (0, 1), (-1, -1), 8),
        ('LEFTPADDING', (0, 1), (-1, -1), 4),
        ('RIGHTPADDING', (0, 1), (-1, -1), 4),
    ])
    table.setStyle(table_style)

    # Calculate Y position to draw the table
    available_height = height - 120
    table_width, table_height = table.wrapOn(pdf, width - 40, available_height)
    x_start = 20
    y_start = available_height - table_height

    table.drawOn(pdf, x_start, y_start)

    # Add summary section
    summary_y = y_start - 80
    
    pdf.setFont("Helvetica-Bold", 14)
    pdf.drawString(40, summary_y, "Weekly Summary")
    
    # Calculate weekly totals
    weekly_total_sales = sum(day['total_sales'] for day in weekly_data)
    weekly_total_orders = sum(day['orders_count'] for day in weekly_data)
    weekly_paid_orders = sum(day['paid_count'] for day in weekly_data)
    weekly_pending_orders = sum(day['pending_count'] for day in weekly_data)
    
    avg_weekly_order_value = weekly_total_sales / weekly_total_orders if weekly_total_orders > 0 else 0
    conversion_rate = (weekly_paid_orders / weekly_total_orders) * 100 if weekly_total_orders > 0 else 0

    pdf.setFont("Helvetica", 10)
    pdf.drawString(40, summary_y - 20, f"Total Weekly Sales: Rs.{weekly_total_sales:,.0f}")
    pdf.drawString(40, summary_y - 35, f"Total Weekly Orders: {weekly_total_orders}")
    pdf.drawString(40, summary_y - 50, f"Paid Orders: {weekly_paid_orders} | Pending Orders: {weekly_pending_orders}")
    pdf.drawString(40, summary_y - 65, f"Average Order Value: Rs.{avg_weekly_order_value:,.0f}")
    pdf.drawString(40, summary_y - 80, f"Payment Conversion Rate: {conversion_rate:.1f}%")
    
    # Best performing day
    best_day = max(weekly_data, key=lambda x: x['total_sales'])
    pdf.drawString(40, summary_y - 100, f"Best Day: {best_day['date'].strftime('%Y-%m-%d')} (Rs.{best_day['total_sales']:,.0f})")

    # Finalize PDF
    pdf.showPage()
    pdf.save()

    return response