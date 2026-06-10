from rest_framework import serializers

from .models import Category


class CategorySerializer(serializers.ModelSerializer):
    full_path = serializers.CharField(read_only=True)

    class Meta:
        model = Category
        fields = ('id', 'org', 'parent', 'name', 'slug', 'kind', 'is_system', 'full_path', 'created_at')
        read_only_fields = ('id', 'slug', 'is_system', 'created_at')

    def validate(self, attrs: dict) -> dict:
        parent = attrs.get('parent')
        org = attrs.get('org')
        if parent is not None and org is not None and parent.org_id != org.id:
            raise serializers.ValidationError({'parent': 'Parent category must belong to the same organisation.'})
        return attrs
