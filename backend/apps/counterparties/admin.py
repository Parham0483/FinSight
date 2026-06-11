from django.contrib import admin

from .models import Counterparty


@admin.register(Counterparty)
class CounterpartyAdmin(admin.ModelAdmin):
    list_display = ('name', 'type', 'org', 'is_auto_created', 'is_merged', 'created_at')
    list_filter = ('type', 'is_auto_created')
    search_fields = ('name', 'normalised_name')
    readonly_fields = ('normalised_name', 'created_at', 'updated_at')
