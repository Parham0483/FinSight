import uuid
from django.db import models
from apps.organisations.models import Organisation


class Customer(models.Model):
    RISK_CHOICES = [
        ('green', 'Green — pays on time'),
        ('amber', 'Amber — occasionally late'),
        ('red', 'Red — chronic late payer'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    org = models.ForeignKey(Organisation, on_delete=models.CASCADE, related_name='customers')
    name = models.CharField(max_length=255)
    email = models.EmailField(blank=True)
    payment_terms_days = models.PositiveIntegerField(default=30)
    risk_score = models.CharField(max_length=10, choices=RISK_CHOICES, default='green')
    avg_days_late = models.DecimalField(max_digits=5, decimal_places=1, default=0)
    risk_updated_at = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'customers'

    def __str__(self) -> str:
        return self.name


class Invoice(models.Model):
    STATUS_CHOICES = [
        ('unpaid', 'Unpaid'),
        ('partial', 'Partially Paid'),
        ('paid', 'Paid'),
        ('overdue', 'Overdue'),
        ('written_off', 'Written Off'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    org = models.ForeignKey(Organisation, on_delete=models.CASCADE, related_name='invoices')
    customer = models.ForeignKey(Customer, on_delete=models.SET_NULL, null=True, related_name='invoices')
    reference = models.CharField(max_length=100, blank=True)
    amount = models.DecimalField(max_digits=15, decimal_places=2)
    currency = models.CharField(max_length=3, default='GBP')
    issue_date = models.DateField()
    due_date = models.DateField()
    paid_date = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=50, choices=STATUS_CHOICES, default='unpaid')
    matched_transaction = models.ForeignKey(
        'transactions.Transaction', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='matched_invoices'
    )
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'invoices'
        indexes = [
            models.Index(fields=['status', 'due_date']),
            models.Index(fields=['customer']),
        ]

    def __str__(self) -> str:
        return f'{self.reference or self.id} — {self.customer} £{self.amount}'
