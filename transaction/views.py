from django.core.paginator import Paginator
from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import render
from .models import Transaction

@staff_member_required
def admin_transaction_list(request):
    transaction_list = Transaction.objects.select_related('user', 'order').order_by('-timestamp')
    paginator = Paginator(transaction_list, 25)  # 25 per page

    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    context = {
        'transactions': page_obj,
        'page_obj': page_obj,
        'is_paginated': page_obj.has_other_pages(),
    }
    return render(request, 'custom_admin/orders/transactions.html', context)
