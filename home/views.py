from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.views.decorators.cache import never_cache
from django.views.decorators.cache import cache_control
from django.contrib.admin.views.decorators import staff_member_required
from products.models import ProductVariant, Product
from django.db.models import OuterRef, Subquery
from orders.models import Order, OrderItem
from django.db.models import Sum, Count
from datetime import date, timedelta
from django.http import HttpResponse
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib import colors
from reportlab.platypus import Table, TableStyle



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
    # Total orders
    total_orders = Order.objects.count()

    # Completed and pending orders
    completed_orders = Order.objects.filter(payment_status="Completed").count()
    pending_orders = Order.objects.filter(payment_status="Pending").count()

    # Total sales (only completed orders)
    total_sales = Order.objects.filter(payment_status="Completed").aggregate(total=Sum("total_price"))["total"] or 0

    # Top 5 selling products
    top_products = (
        OrderItem.objects.values("variant__product__name")
        .annotate(quantity_sold=Sum("quantity"))
        .order_by("-quantity_sold")[:5]
    )

    # Daily sales for last 7 days
    today = date.today()
    last_7_days = [today - timedelta(days=i) for i in range(6, -1, -1)]
    daily_sales = []
    for day in last_7_days:
        day_sales = Order.objects.filter(payment_status="Completed", created_at__date=day).aggregate(total=Sum("total_price"))["total"] or 0
        daily_sales.append({"date": day.strftime("%b %d"), "sales": day_sales})

    # Example recent activity (you can customize as needed)
    recent_activity = [
        "You placed an order on Aug 20",
        "Your profile was updated",
        "You received a message from Support"
    ]

    context = {
        "total_orders": total_orders,
        "completed_orders": completed_orders,
        "pending_orders": pending_orders,
        "total_sales": total_sales,
        "top_products": top_products,
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
    table_data = [['Date', 'Total Sales (₹)', 'Orders Count', 'Top Products']]

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