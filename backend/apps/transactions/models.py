import uuid
from django.db import models
from django.contrib.postgres.fields import ArrayField
from apps.banking.models import BankAccount


class Transaction(models.Model):
    CATEGORY_CHOICES = [
        ('supplier_payment', 'Supplier Payment'),
        ('customer_receipt', 'Customer Receipt'),
        ('payroll', 'Payroll'),
        ('tax', 'Tax'),
        ('rent_overhead', 'Rent / Overhead'),
        ('fx_transfer', 'FX Transfer'),
        ('bank_fee', 'Bank Fee'),
        ('loan_repayment', 'Loan Repayment'),
        ('other', 'Other'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    account = models.ForeignKey(BankAccount, on_delete=models.CASCADE, related_name='transactions')
    truelayer_transaction_id = models.CharField(max_length=255, unique=True)
    timestamp = models.DateTimeField(db_index=True)
    description = models.TextField(blank=True)
    # Positive = inflow, negative = outflow
    amount = models.DecimalField(max_digits=15, decimal_places=2)
    currency = models.CharField(max_length=3, default='GBP')
    merchant_name = models.CharField(max_length=255, blank=True)
    category = models.CharField(max_length=100, choices=CATEGORY_CHOICES, default='other')
    category_overridden = models.BooleanField(default=False)
    is_recurring = models.BooleanField(default=False)
    recurring_group_id = models.UUIDField(null=True, blank=True, db_index=True)
    tags = ArrayField(models.CharField(max_length=100), default=list, blank=True)
    raw_data = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'transactions'
        indexes = [
            models.Index(fields=['account', '-timestamp']),
            models.Index(fields=['category']),
            models.Index(fields=['is_recurring', 'recurring_group_id']),
        ]

    def __str__(self) -> str:
        direction = 'IN' if self.amount > 0 else 'OUT'
        return f'{direction} {abs(self.amount)} {self.currency} — {self.description[:40]}'
