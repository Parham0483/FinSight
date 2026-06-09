from django.contrib import admin
from .models import Document, DocumentLineItem, DocumentStorageSettings


class DocumentLineItemInline(admin.TabularInline):
    model = DocumentLineItem
    extra = 0
    fields = ('description', 'quantity', 'unit_price', 'total', 'currency', 'tax_amount')


@admin.register(Document)
class DocumentAdmin(admin.ModelAdmin):
    list_display = (
        'original_filename', 'org', 'document_type', 'status',
        'processing_tier_used', 'confidence_score', 'tokens_used', 'uploaded_at',
    )
    list_filter = ('document_type', 'status', 'processing_tier_used')
    search_fields = ('original_filename', 'org__name')
    date_hierarchy = 'uploaded_at'
    readonly_fields = ('extracted_data', 'confirmed_data', 'tokens_used', 'processing_tier_used', 'confidence_score')
    inlines = [DocumentLineItemInline]


@admin.register(DocumentStorageSettings)
class DocumentStorageSettingsAdmin(admin.ModelAdmin):
    list_display = ('org', 'backend', 'configured_at')
    list_filter = ('backend',)
