import uuid
from django.db import models
from apps.organisations.models import Organisation


class FxRate(models.Model):
    SOURCE_CHOICES = [
        ('exchangerate-api', 'ExchangeRate-API'),
        ('alpha_vantage', 'Alpha Vantage'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    base_currency = models.CharField(max_length=3)
    quote_currency = models.CharField(max_length=3)
    rate = models.DecimalField(max_digits=15, decimal_places=6)
    source = models.CharField(max_length=50, choices=SOURCE_CHOICES)
    fetched_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'fx_rates'
        indexes = [
            models.Index(fields=['base_currency', 'quote_currency', '-fetched_at']),
        ]

    def __str__(self) -> str:
        return f'{self.base_currency}/{self.quote_currency} = {self.rate}'


class FxAlert(models.Model):
    DIRECTION_CHOICES = [
        ('up', 'Strengthens'),
        ('down', 'Weakens'),
        ('either', 'Either direction'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    org = models.ForeignKey(Organisation, on_delete=models.CASCADE, related_name='fx_alerts')
    base_currency = models.CharField(max_length=3, default='GBP')
    quote_currency = models.CharField(max_length=3)
    threshold_percent = models.DecimalField(max_digits=5, decimal_places=2)
    direction = models.CharField(max_length=10, choices=DIRECTION_CHOICES, default='either')
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = 'fx_alerts'
