from django.contrib import admin

from .models import Counterparty, Invoice


@admin.register(Counterparty)
class CounterpartyAdmin(admin.ModelAdmin):
    list_display = ('name', 'type', 'org', 'is_auto_created', 'is_merged', 'created_at')
    list_filter = ('type', 'is_auto_created')
    search_fields = ('name', 'normalised_name')
    readonly_fields = ('normalised_name', 'created_at', 'updated_at')


@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    list_display = ('reference', 'counterparty', 'amount', 'currency', 'due_date', 'status')
    list_filter = ('status', 'currency')
    search_fields = ('reference', 'counterparty__name')
    date_hierarchy = 'due_date'
