from rest_framework import serializers
from .models import Document, DocumentLineItem, DocumentStorageSettings

ALLOWED_MIME_TYPES = {
    'application/pdf',
    'image/jpeg', 'image/jpg', 'image/png',
    'image/webp', 'image/heic', 'image/tiff',
    'image/bmp',
}

MAX_FILE_SIZE_BYTES = 25 * 1024 * 1024  # 25 MB


class DocumentUploadSerializer(serializers.Serializer):
    file = serializers.FileField()
    document_type = serializers.ChoiceField(choices=[
        'invoice', 'bank_statement', 'receipt', 'cheque', 'purchase_order', 'other',
    ])

    def validate_file(self, value):
        if value.size > MAX_FILE_SIZE_BYTES:
            raise serializers.ValidationError(
                f'File too large. Maximum size is 25 MB (yours: {value.size // (1024*1024)} MB).'
            )

        mime = getattr(value, 'content_type', '') or ''
        if mime not in ALLOWED_MIME_TYPES:
            raise serializers.ValidationError(
                f'Unsupported file type: {mime}. '
                f'Accepted: PDF, JPEG, PNG, WebP, HEIC, TIFF, BMP.'
            )
        return value


class DocumentLineItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = DocumentLineItem
        fields = ('id', 'description', 'quantity', 'unit_price', 'total', 'currency', 'tax_amount', 'sort_order')


class DocumentSerializer(serializers.ModelSerializer):
    line_items = DocumentLineItemSerializer(many=True, read_only=True)
    match_info = serializers.SerializerMethodField()

    class Meta:
        model = Document
        fields = (
            'id', 'document_type', 'status', 'original_filename',
            'file_size_bytes', 'mime_type',
            'processing_tier_used', 'tokens_used', 'confidence_score',
            'extracted_data', 'confirmed_data', 'review_notes',
            'line_items', 'match_info',
            'uploaded_at', 'processed_at', 'confirmed_at',
            'created_invoice_id', 'created_transaction_id', 'created_customer_id',
        )
        read_only_fields = (
            'id', 'status', 'processing_tier_used', 'tokens_used', 'confidence_score',
            'extracted_data', 'uploaded_at', 'processed_at', 'confirmed_at',
        )

    def get_match_info(self, obj: Document) -> dict:
        if obj.extracted_data and '_match' in obj.extracted_data:
            return obj.extracted_data['_match']
        return {}


class DocumentConfirmSerializer(serializers.Serializer):
    """User confirms (with optional corrections) the extracted data."""
    confirmed_data = serializers.JSONField()
    review_notes = serializers.CharField(allow_blank=True, default='')
    create_invoice = serializers.BooleanField(default=False)
    create_transaction = serializers.BooleanField(default=False)
    create_customer = serializers.BooleanField(default=False)


class StorageSettingsSerializer(serializers.ModelSerializer):
    backend_description = serializers.SerializerMethodField()
    # Never expose encrypted keys in API response
    s3_access_key_encrypted = serializers.SerializerMethodField()
    s3_secret_key_encrypted = serializers.SerializerMethodField()
    supabase_key_encrypted = serializers.SerializerMethodField()

    class Meta:
        model = DocumentStorageSettings
        fields = (
            'backend', 'backend_description',
            's3_bucket', 's3_region', 's3_endpoint_url',
            's3_access_key_encrypted', 's3_secret_key_encrypted',
            'supabase_url', 'supabase_bucket', 'supabase_key_encrypted',
            'configured_at',
        )

    def get_backend_description(self, obj) -> str:
        return DocumentStorageSettings.BACKEND_DESCRIPTIONS.get(obj.backend, '')

    def get_s3_access_key_encrypted(self, obj) -> str:
        return '••••••' if obj.s3_access_key_encrypted else ''

    def get_s3_secret_key_encrypted(self, obj) -> str:
        return '••••••' if obj.s3_secret_key_encrypted else ''

    def get_supabase_key_encrypted(self, obj) -> str:
        return '••••••' if obj.supabase_key_encrypted else ''


class StorageSettingsUpdateSerializer(serializers.ModelSerializer):
    s3_access_key = serializers.CharField(write_only=True, required=False, allow_blank=True)
    s3_secret_key = serializers.CharField(write_only=True, required=False, allow_blank=True)
    supabase_key = serializers.CharField(write_only=True, required=False, allow_blank=True)

    class Meta:
        model = DocumentStorageSettings
        fields = (
            'backend',
            's3_bucket', 's3_region', 's3_endpoint_url',
            's3_access_key',  's3_secret_key',
            'supabase_url', 'supabase_bucket', 'supabase_key',
        )

    def update(self, instance, validated_data):
        from core.utils.encryption import encrypt

        if key := validated_data.pop('s3_access_key', None):
            validated_data['s3_access_key_encrypted'] = encrypt(key)
        if key := validated_data.pop('s3_secret_key', None):
            validated_data['s3_secret_key_encrypted'] = encrypt(key)
        if key := validated_data.pop('supabase_key', None):
            validated_data['supabase_key_encrypted'] = encrypt(key)

        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        return instance
