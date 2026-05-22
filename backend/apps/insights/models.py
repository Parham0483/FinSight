import uuid
from django.db import models
from apps.organisations.models import Organisation


class AIInsight(models.Model):
    FLAG_CHOICES = [
        ('healthy', 'Healthy'),
        ('watch', 'Watch'),
        ('warning', 'Warning'),
        ('critical', 'Critical'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    org = models.ForeignKey(Organisation, on_delete=models.CASCADE, related_name='insights')
    generated_at = models.DateTimeField(auto_now_add=True)
    forecast_flag = models.CharField(max_length=20, choices=FLAG_CHOICES, default='healthy')
    daily_briefing = models.TextField()
    cash_position_summary = models.TextField(blank=True)
    top_risk = models.JSONField(null=True, blank=True)
    opportunities = models.JSONField(default=list)
    chase_list = models.JSONField(default=list)
    fx_alert = models.TextField(blank=True)
    week_ahead = models.TextField(blank=True)
    raw_response = models.JSONField(default=dict)
    generation_cost_tokens = models.PositiveIntegerField(default=0)

    class Meta:
        db_table = 'ai_insights'
        ordering = ['-generated_at']

    def __str__(self) -> str:
        return f'{self.org.name} insight @ {self.generated_at:%Y-%m-%d}'
