import uuid
from django.db import models
from apps.organisations.models import Organisation


class ForecastRun(models.Model):
    STATUS_CHOICES = [
        ('running', 'Running'),
        ('complete', 'Complete'),
        ('failed', 'Failed'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    org = models.ForeignKey(Organisation, on_delete=models.CASCADE, related_name='forecast_runs')
    run_at = models.DateTimeField(auto_now_add=True)
    horizon_days = models.PositiveIntegerField(default=90)
    algorithm_version = models.CharField(max_length=20, default='1.0')
    status = models.CharField(max_length=50, choices=STATUS_CHOICES, default='running')
    metadata = models.JSONField(default=dict)

    class Meta:
        db_table = 'forecast_runs'

    def __str__(self) -> str:
        return f'Forecast {self.org.name} @ {self.run_at:%Y-%m-%d %H:%M}'


class ForecastDataPoint(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    run = models.ForeignKey(ForecastRun, on_delete=models.CASCADE, related_name='data_points')
    forecast_date = models.DateField()
    predicted_inflow = models.DecimalField(max_digits=15, decimal_places=2, null=True)
    predicted_outflow = models.DecimalField(max_digits=15, decimal_places=2, null=True)
    predicted_net = models.DecimalField(max_digits=15, decimal_places=2, null=True)
    predicted_balance = models.DecimalField(max_digits=15, decimal_places=2, null=True)
    confidence_score = models.DecimalField(max_digits=4, decimal_places=3, null=True)
    confidence_band_low = models.DecimalField(max_digits=15, decimal_places=2, null=True)
    confidence_band_high = models.DecimalField(max_digits=15, decimal_places=2, null=True)
    committed_inflow = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    committed_outflow = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    layer_breakdown = models.JSONField(default=dict)
    committed_items = models.JSONField(default=list)

    class Meta:
        db_table = 'forecast_data_points'
        indexes = [
            models.Index(fields=['run', 'forecast_date']),
        ]
        unique_together = ('run', 'forecast_date')


class ForecastScenario(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    org = models.ForeignKey(Organisation, on_delete=models.CASCADE, related_name='scenarios')
    name = models.CharField(max_length=255)
    base_run = models.ForeignKey(ForecastRun, on_delete=models.SET_NULL, null=True)
    parameters = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'forecast_scenarios'
