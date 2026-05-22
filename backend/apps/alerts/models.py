import uuid
from django.db import models
from apps.organisations.models import Organisation


class Alert(models.Model):
    TYPE_CHOICES = [
        ('low_balance', 'Low Balance'),
        ('overdue_invoice', 'Overdue Invoice'),
        ('fx_movement', 'FX Rate Movement'),
        ('large_outflow', 'Large Upcoming Outflow'),
        ('anomaly', 'Unusual Transaction'),
        ('consent_expiry', 'Bank Connection Expiring'),
        ('forecast_warning', 'Forecast Warning'),
    ]

    SEVERITY_CHOICES = [
        ('info', 'Info'),
        ('warning', 'Warning'),
        ('critical', 'Critical'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    org = models.ForeignKey(Organisation, on_delete=models.CASCADE, related_name='alerts')
    alert_type = models.CharField(max_length=50, choices=TYPE_CHOICES)
    severity = models.CharField(max_length=20, choices=SEVERITY_CHOICES, default='info')
    title = models.CharField(max_length=255)
    body = models.TextField(blank=True)
    metadata = models.JSONField(default=dict)
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'alerts'
        indexes = [
            models.Index(fields=['org', 'is_read', '-created_at']),
        ]
        ordering = ['-created_at']

    def __str__(self) -> str:
        return f'[{self.severity.upper()}] {self.title}'


class AlertSettings(models.Model):
    """Per-org configurable alert thresholds."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    org = models.OneToOneField(Organisation, on_delete=models.CASCADE, related_name='alert_settings')
    low_balance_threshold = models.DecimalField(max_digits=15, decimal_places=2, default=5000)
    large_outflow_threshold = models.DecimalField(max_digits=15, decimal_places=2, default=2000)
    overdue_days_threshold = models.PositiveIntegerField(default=7)
    fx_movement_percent = models.DecimalField(max_digits=5, decimal_places=2, default=1.0)
    email_daily_digest = models.BooleanField(default=True)
    email_weekly_digest = models.BooleanField(default=True)

    class Meta:
        db_table = 'alert_settings'
