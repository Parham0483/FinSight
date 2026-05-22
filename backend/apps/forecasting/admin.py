from django.contrib import admin
from .models import ForecastDataPoint, ForecastRun, ForecastScenario

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
