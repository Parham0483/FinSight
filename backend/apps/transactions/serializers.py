from decimal import Decimal

from rest_framework import serializers

from apps.categories.models import Category
from apps.counterparties.models import Counterparty

from .models import Transaction


class TransactionSerializer(serializers.ModelSerializer):
    """Read/update representation with friendly nested labels."""

    direction = serializers.CharField(read_only=True)
    counterparty_name = serializers.CharField(source='counterparty.name', read_only=True, default=None)
    category_name = serializers.CharField(source='category.name', read_only=True, default=None)

    class Meta:
        model = Transaction
        fields = (
            'id', 'org', 'account', 'source', 'external_id', 'confidence',
            'timestamp', 'description', 'amount', 'currency',
            'base_amount', 'base_currency', 'fx_rate',
            'merchant_name', 'counterparty', 'counterparty_name',
            'category', 'category_name', 'category_overridden',
            'direction', 'is_recurring', 'recurring_group_id', 'tags',
            'dedup_hash', 'created_at', 'updated_at',
        )
        read_only_fields = (
            'id', 'org', 'source', 'direction', 'dedup_hash',
            'created_at', 'updated_at',
        )


class TransactionCreateSerializer(serializers.Serializer):
    """Manual single-transaction entry — validated, then routed through the
    ManualEntrySource so it shares the same pipeline as every other source."""

    timestamp = serializers.DateTimeField()
    amount = serializers.DecimalField(max_digits=15, decimal_places=2)
    currency = serializers.CharField(max_length=3, required=False, allow_blank=True)
    description = serializers.CharField(required=False, allow_blank=True, default='')
    counterparty_name = serializers.CharField(required=False, allow_blank=True, default='')
    counterparty_type = serializers.ChoiceField(
        choices=[c[0] for c in Counterparty.TYPE_CHOICES],
        required=False, default=Counterparty.TYPE_OTHER,
    )
    merchant_name = serializers.CharField(required=False, allow_blank=True, default='')
    category_slug = serializers.CharField(required=False, allow_blank=True, allow_null=True, default=None)

    def validate_amount(self, value: Decimal) -> Decimal:
        if value == 0:
            raise serializers.ValidationError('Transaction amount cannot be zero.')
        return value


class CsvImportSerializer(serializers.Serializer):
    """CSV import payload: raw text plus either a named preset or a column map."""

    content = serializers.CharField(trim_whitespace=False)
    preset = serializers.CharField(required=False, allow_null=True, default=None)
    column_map = serializers.DictField(
        child=serializers.CharField(), required=False, allow_null=True, default=None,
    )

    def validate(self, attrs: dict) -> dict:
        if not attrs.get('content', '').strip():
            raise serializers.ValidationError({'content': 'CSV content is empty.'})
        return attrs
