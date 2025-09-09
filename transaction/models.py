from django.db import models
from django.contrib.auth.models import User
from decimal import Decimal
import random

class Transaction(models.Model):
    TRANSACTION_TYPE_CHOICES = [
        ('WALLET_DEBIT', 'Wallet Debit'),
        ('WALLET_CREDIT', 'Wallet Credit'),
        ('COD', 'Cash on Delivery'),
        ('ONLINE_PAYMENT', 'Online Payment'),
    ]
    PAYMENT_STATUS_CHOICES = [
        ('Debit', 'Debit'),
        ('Credit', 'Credit'),
        ('Failed', 'Failed'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE)
    transaction_type = models.CharField(max_length=15, choices=TRANSACTION_TYPE_CHOICES)
    payment_status = models.CharField(max_length=10, choices=PAYMENT_STATUS_CHOICES, default='Pending')
    amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    description = models.TextField(blank=True)
    order = models.ForeignKey('orders.Order', on_delete=models.SET_NULL, blank=True, null=True)
    timestamp = models.DateTimeField(auto_now_add=True)
    transaction_id = models.CharField(max_length=14, unique=True, blank=True, null=True)

    class Meta:
        ordering = ['-timestamp']
        verbose_name = 'Admin Transaction'
        verbose_name_plural = 'Admin Transactions'

    def __str__(self):
        return f"{self.user.username} - {self.transaction_type} - ₹{self.amount} on {self.timestamp.strftime('%Y-%m-%d %H:%M')}"

    def save(self, *args, **kwargs):
        if not self.transaction_id:
            self.transaction_id = self.generate_unique_transaction_id()
        super().save(*args, **kwargs)

    def generate_unique_transaction_id(self):
        while True:
            transaction_id = str(random.randint(10**13, 10**14 - 1))
            if not Transaction.objects.filter(transaction_id=transaction_id).exists():
                return transaction_id
