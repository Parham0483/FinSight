import uuid
from django.db import models
from apps.organisations.models import Organisation


class BankConnection(models.Model):
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('expired', 'Expired'),
        ('revoked', 'Revoked'),
        ('error', 'Error'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    org = models.ForeignKey(Organisation, on_delete=models.CASCADE, related_name='bank_connections')
    provider_id = models.CharField(max_length=100, blank=True)
    provider_name = models.CharField(max_length=255, blank=True)
    # Tokens encrypted at rest via Fernet
    access_token_encrypted = models.TextField()
    refresh_token_encrypted = models.TextField()
    token_expires_at = models.DateTimeField(null=True, blank=True)
    consent_expires_at = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=50, choices=STATUS_CHOICES, default='active')
    last_synced_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'bank_connections'

    def __str__(self) -> str:
        return f'{self.provider_name} ({self.org.name})'


class BankAccount(models.Model):
    ACCOUNT_TYPE_CHOICES = [
        ('TRANSACTION', 'Current / Transaction'),
        ('SAVINGS', 'Savings'),
        ('CREDIT_CARD', 'Credit Card'),
        ('MERCHANT', 'Merchant'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    connection = models.ForeignKey(BankConnection, on_delete=models.CASCADE, related_name='accounts')
    truelayer_account_id = models.CharField(max_length=255, unique=True)
    account_type = models.CharField(max_length=50, choices=ACCOUNT_TYPE_CHOICES, blank=True)
    display_name = models.CharField(max_length=255, blank=True)
    currency = models.CharField(max_length=3, default='GBP')
    account_number = models.CharField(max_length=20, blank=True)
    sort_code = models.CharField(max_length=10, blank=True)
    iban = models.CharField(max_length=34, blank=True)
    current_balance = models.DecimalField(max_digits=15, decimal_places=2, null=True)
    available_balance = models.DecimalField(max_digits=15, decimal_places=2, null=True)
    balance_updated_at = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = 'bank_accounts'

    def __str__(self) -> str:
        return f'{self.display_name} ({self.currency})'


class DirectDebit(models.Model):
    """Standing orders and direct debits from TrueLayer /direct_debits endpoint."""

    FREQUENCY_CHOICES = [
        ('weekly', 'Weekly'),
        ('monthly', 'Monthly'),
        ('quarterly', 'Quarterly'),
        ('annually', 'Annually'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    account = models.ForeignKey(BankAccount, on_delete=models.CASCADE, related_name='direct_debits')
    truelayer_mandate_id = models.CharField(max_length=255, unique=True)
    merchant_name = models.CharField(max_length=255, blank=True)
    amount = models.DecimalField(max_digits=15, decimal_places=2)
    currency = models.CharField(max_length=3, default='GBP')
    frequency = models.CharField(max_length=20, choices=FREQUENCY_CHOICES, default='monthly')
    day_of_month = models.SmallIntegerField(null=True, blank=True)
    next_payment_date = models.DateField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    raw_data = models.JSONField(default=dict)

    class Meta:
        db_table = 'direct_debits'

    def get_next_dates(self, horizon_days: int) -> list:
        """Return list of upcoming payment dates within the horizon."""
        from datetime import date, timedelta
        if not self.next_payment_date:
            return []

        dates = []
        current = self.next_payment_date
        end = date.today() + timedelta(days=horizon_days)

        while current <= end:
            if current >= date.today():
                dates.append(current)
            if self.frequency == 'monthly':
                month = current.month + 1
                year = current.year + (month - 1) // 12
                month = ((month - 1) % 12) + 1
                try:
                    current = current.replace(year=year, month=month)
                except ValueError:
                    break
            elif self.frequency == 'weekly':
                current = current + timedelta(weeks=1)
            elif self.frequency == 'quarterly':
                month = current.month + 3
                year = current.year + (month - 1) // 12
                month = ((month - 1) % 12) + 1
                try:
                    current = current.replace(year=year, month=month)
                except ValueError:
                    break
            elif self.frequency == 'annually':
                try:
                    current = current.replace(year=current.year + 1)
                except ValueError:
                    break
            else:
                break

        return dates
