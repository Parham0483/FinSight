from django.contrib import admin
from .models import Transaction

@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display = ('timestamp', 'amount', 'currency', 'merchant_name', 'category', 'is_recurring')
    list_filter = ('category', 'currency', 'is_recurring')
    search_fields = ('description', 'merchant_name')
    date_hierarchy = 'timestamp'
