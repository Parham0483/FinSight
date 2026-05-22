from django.contrib import admin
from .models import AIInsight

@admin.register(AIInsight)
class AIInsightAdmin(admin.ModelAdmin):
    list_display = ('org', 'generated_at', 'forecast_flag', 'generation_cost_tokens')
    list_filter = ('forecast_flag',)
    search_fields = ('org__name',)
    date_hierarchy = 'generated_at'
