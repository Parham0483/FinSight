from django.contrib import admin
from .models import Bill, ForecastDataPoint, ForecastRun, ForecastScenario, RecurringObligation

@admin.register(ForecastRun)
class ForecastRunAdmin(admin.ModelAdmin):
    list_display = ('org', 'run_at', 'horizon_days', 'status', 'algorithm_version')
    list_filter = ('status',)
    search_fields = ('org__name',)

@admin.register(ForecastDataPoint)
class ForecastDataPointAdmin(admin.ModelAdmin):
    list_display = ('run', 'forecast_date', 'predicted_balance', 'confidence_score')
    date_hierarchy = 'forecast_date'

@admin.register(ForecastScenario)
class ForecastScenarioAdmin(admin.ModelAdmin):
    list_display = ('org', 'name', 'created_at')
    search_fields = ('org__name', 'name')

@admin.register(Bill)
class BillAdmin(admin.ModelAdmin):
    list_display = ('org', 'counterparty', 'amount', 'currency', 'due_date', 'status')
    list_filter = ('status', 'currency')
    date_hierarchy = 'due_date'
    search_fields = ('reference', 'counterparty__name')

@admin.register(RecurringObligation)
class RecurringObligationAdmin(admin.ModelAdmin):
    list_display = ('org', 'kind', 'amount', 'currency', 'frequency', 'is_active', 'source')
    list_filter = ('kind', 'frequency', 'is_active', 'source')
    search_fields = ('description', 'counterparty__name')
