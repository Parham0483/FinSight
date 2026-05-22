from django.contrib import admin
from .models import FxAlert, FxRate

@admin.register(FxRate)
class FxRateAdmin(admin.ModelAdmin):
    list_display = ('base_currency', 'quote_currency', 'rate', 'source', 'fetched_at')
    list_filter = ('base_currency', 'quote_currency', 'source')
    date_hierarchy = 'fetched_at'

@admin.register(FxAlert)
class FxAlertAdmin(admin.ModelAdmin):
    list_display = ('org', 'base_currency', 'quote_currency', 'threshold_percent', 'direction', 'is_active')
    list_filter = ('direction', 'is_active')
