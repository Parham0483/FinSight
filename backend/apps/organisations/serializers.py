from rest_framework import serializers
from .models import Organisation


class OrganisationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Organisation
        fields = ('id', 'name', 'industry', 'country_code', 'base_currency', 'timezone', 'locale', 'is_demo', 'created_at')
        read_only_fields = ('id', 'is_demo', 'created_at')


class OrganisationCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Organisation
        fields = ('name', 'industry', 'country_code', 'base_currency', 'timezone')

    def validate_name(self, value: str) -> str:
        if not value.strip():
            raise serializers.ValidationError('Business name cannot be blank.')
        return value.strip()
