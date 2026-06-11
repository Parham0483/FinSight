from rest_framework import serializers

from .models import Counterparty


class CounterpartySerializer(serializers.ModelSerializer):
    is_merged = serializers.BooleanField(read_only=True)

    class Meta:
        model = Counterparty
        fields = (
            'id', 'org', 'name', 'normalised_name', 'type', 'tags',
            'country_code', 'email', 'is_auto_created', 'merged_into',
            'is_merged', 'notes', 'created_at', 'updated_at',
        )
        read_only_fields = (
            'id', 'org', 'normalised_name', 'is_auto_created', 'is_merged',
            'created_at', 'updated_at',
        )

    def validate_type(self, value: str) -> str:
        valid = {choice[0] for choice in Counterparty.TYPE_CHOICES}
        if value not in valid:
            raise serializers.ValidationError(f'Invalid type. Choose one of: {", ".join(sorted(valid))}.')
        return value

    def validate_merged_into(self, value: Counterparty | None) -> Counterparty | None:
        if value is None:
            return value
        org = self.instance.org if self.instance else None
        if org is not None and value.org_id != org.id:
            raise serializers.ValidationError('Cannot merge into a counterparty from another organisation.')
        if self.instance is not None and value.id == self.instance.id:
            raise serializers.ValidationError('A counterparty cannot be merged into itself.')
        return value


class MergeSerializer(serializers.Serializer):
    """Payload for POST /counterparties/{id}/merge/ — id of the survivor."""
    target = serializers.UUIDField()
