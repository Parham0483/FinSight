import uuid
from django.db import models
from apps.organisations.models import Organisation
from apps.authentication.models import User


class Document(models.Model):
    TYPE_CHOICES = [
        ('invoice', 'Invoice'),
        ('bank_statement', 'Bank Statement'),
        ('receipt', 'Receipt'),
        ('cheque', 'Cheque'),
        ('purchase_order', 'Purchase Order'),
        ('other', 'Other'),
    ]

    STATUS_CHOICES = [
        ('pending', 'Pending — queued for processing'),
        ('preprocessing', 'Preprocessing image'),
        ('extracting', 'Extracting data'),
        ('review', 'Awaiting human review'),
        ('confirmed', 'Confirmed — data committed'),
        ('rejected', 'Rejected by user'),
        ('failed', 'Processing failed'),
    ]

    TIER_CHOICES = [
        (1, 'Tier 1 — PDF text (free)'),
        (2, 'Tier 2 — Haiku text'),
        (3, 'Tier 3 — Haiku vision'),
        (4, 'Tier 4 — Sonnet vision'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    org = models.ForeignKey(Organisation, on_delete=models.CASCADE, related_name='documents')
    uploaded_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='uploaded_documents')

    # File storage — path is relative, resolved via storage backend
    file_path = models.TextField()
    original_filename = models.CharField(max_length=500)
    file_size_bytes = models.PositiveIntegerField(default=0)
    mime_type = models.CharField(max_length=100, blank=True)

    document_type = models.CharField(max_length=50, choices=TYPE_CHOICES, default='other')
    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default='pending')

    # Processing metadata
    processing_tier_used = models.SmallIntegerField(choices=TIER_CHOICES, null=True, blank=True)
    tokens_used = models.PositiveIntegerField(default=0)
    confidence_score = models.DecimalField(max_digits=4, decimal_places=3, null=True, blank=True)
    processing_error = models.TextField(blank=True)

    # Extracted data — raw structured output from Claude
    extracted_data = models.JSONField(null=True, blank=True)

    # After human review — confirmed fields (may differ from extracted if user corrected)
    confirmed_data = models.JSONField(null=True, blank=True)

    # Links to created records after confirmation
    created_invoice_id = models.UUIDField(null=True, blank=True)
    created_transaction_id = models.UUIDField(null=True, blank=True)
    created_customer_id = models.UUIDField(null=True, blank=True)

    # Review notes from user
    review_notes = models.TextField(blank=True)

    uploaded_at = models.DateTimeField(auto_now_add=True)
    processed_at = models.DateTimeField(null=True, blank=True)
    confirmed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'documents'
        ordering = ['-uploaded_at']
        indexes = [
            models.Index(fields=['org', 'status']),
            models.Index(fields=['org', 'document_type']),
        ]

    def __str__(self) -> str:
        return f'{self.document_type} — {self.original_filename} ({self.status})'


class DocumentLineItem(models.Model):
    """Line items extracted from invoices and purchase orders."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    document = models.ForeignKey(Document, on_delete=models.CASCADE, related_name='line_items')
    description = models.TextField(blank=True)
    quantity = models.DecimalField(max_digits=12, decimal_places=4, null=True, blank=True)
    unit_price = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
    total = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
    currency = models.CharField(max_length=3, default='GBP')
    tax_amount = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
    sort_order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        db_table = 'document_line_items'
        ordering = ['sort_order']


class DocumentStorageSettings(models.Model):
    """Per-org storage backend choice for uploaded documents."""

    BACKEND_CHOICES = [
        ('local', 'Local filesystem — stored on this server'),
        ('s3', 'AWS S3 / Cloudflare R2 / DigitalOcean Spaces'),
        ('supabase', 'Supabase Storage'),
    ]

    BACKEND_DESCRIPTIONS = {
        'local': (
            'Files stored on the server disk. '
            'Simple, free, works immediately. '
            'Risk: if server disk fails without backup, files are lost. '
            'Best for: getting started, low document volume.'
        ),
        's3': (
            'Files stored in an S3-compatible cloud bucket (AWS, Cloudflare R2 free tier, DigitalOcean). '
            'Highly durable (99.999999999%), scales to millions of documents. '
            'Requires: bucket credentials. '
            'Best for: any business handling sensitive financial documents at volume.'
        ),
        'supabase': (
            'Files stored in Supabase Storage with row-level security. '
            'Integrates with Supabase database if you use it. '
            'Best for: teams already on Supabase.'
        ),
    }

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    org = models.OneToOneField(Organisation, on_delete=models.CASCADE, related_name='storage_settings')
    backend = models.CharField(max_length=20, choices=BACKEND_CHOICES, default='local')

    # S3/compatible settings (encrypted in DB)
    s3_bucket = models.CharField(max_length=255, blank=True)
    s3_region = models.CharField(max_length=50, blank=True)
    s3_access_key_encrypted = models.TextField(blank=True)
    s3_secret_key_encrypted = models.TextField(blank=True)
    s3_endpoint_url = models.URLField(blank=True, help_text='Leave blank for AWS. Set for R2/DO Spaces.')

    # Supabase settings
    supabase_url = models.URLField(blank=True)
    supabase_bucket = models.CharField(max_length=255, blank=True)
    supabase_key_encrypted = models.TextField(blank=True)

    configured_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'document_storage_settings'
