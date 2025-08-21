from django.db import models
from decimal import Decimal
from django.contrib.auth.models import User

class Wallet(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="wallet")
    balance = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0.00"))
    
    def credit(self, amount, description=""):
        self.balance += amount
        self.save()
        WalletTransaction.objects.create(wallet=self, transaction_type="CREDIT", amount=amount, description=description)
        
    def __str__(self):
        return f"{self.user.username} - Balance: {self.balance}"
    def debit(self, amount):
        if self.balance >= amount:
            self.balance -= amount
            self.save()
            return True
        return False
        
        
        
class WalletTransaction(models.Model):
    TRANSACTION_TYPES = (
        ("CREDIT", "Credit"),
    )
    wallet = models.ForeignKey(Wallet, on_delete=models.CASCADE, related_name="transactions")
    transaction_type = models.CharField(max_length=6, choices=TRANSACTION_TYPES)
    product_quantity = models.PositiveIntegerField(default=1)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    description = models.CharField(max_length=255, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"{self.transaction_type} - {self.amount} ({self.wallet.user.username})"
