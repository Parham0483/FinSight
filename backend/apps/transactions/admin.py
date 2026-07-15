from django.contrib import admin

from .models import Transaction


@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display = ('timestamp', 'amount', 'currency', 'source', 'counterparty', 'category', 'is_recurring')
    list_filter = ('source', 'currency', 'is_recurring')
    search_fields = ('description', 'merchant_name')
    raw_id_fields = ('org', 'account', 'counterparty', 'category')
    readonly_fields = ('dedup_hash', 'created_at', 'updated_at')
    date_hierarchy = 'timestamp'
