from django.contrib import admin
from .models import Customer, Invoice

@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = ('name', 'org', 'risk_score', 'avg_days_late', 'payment_terms_days')
    list_filter = ('risk_score',)
    search_fields = ('name', 'email')

@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    list_display = ('reference', 'customer', 'amount', 'currency', 'due_date', 'status')
    list_filter = ('status', 'currency')
    search_fields = ('reference', 'customer__name')
    date_hierarchy = 'due_date'
