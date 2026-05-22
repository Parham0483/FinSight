from django.contrib import admin
from .models import BankAccount, BankConnection, DirectDebit

@admin.register(BankConnection)
class BankConnectionAdmin(admin.ModelAdmin):
    list_display = ('org', 'provider_name', 'status', 'last_synced_at', 'consent_expires_at')
    list_filter = ('status',)
    search_fields = ('org__name', 'provider_name')

@admin.register(BankAccount)
class BankAccountAdmin(admin.ModelAdmin):
    list_display = ('display_name', 'currency', 'current_balance', 'is_active', 'balance_updated_at')
    list_filter = ('currency', 'is_active', 'account_type')
    search_fields = ('display_name',)

@admin.register(DirectDebit)
class DirectDebitAdmin(admin.ModelAdmin):
    list_display = ('merchant_name', 'amount', 'currency', 'frequency', 'next_payment_date', 'is_active')
    list_filter = ('frequency', 'is_active', 'currency')
