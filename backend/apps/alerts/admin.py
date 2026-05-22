from django.contrib import admin
from .models import Alert, AlertSettings

@admin.register(Alert)
class AlertAdmin(admin.ModelAdmin):
    list_display = ('title', 'org', 'alert_type', 'severity', 'is_read', 'created_at')
    list_filter = ('alert_type', 'severity', 'is_read')
    search_fields = ('title', 'org__name')

@admin.register(AlertSettings)
class AlertSettingsAdmin(admin.ModelAdmin):
    list_display = ('org', 'low_balance_threshold', 'large_outflow_threshold', 'email_daily_digest')
