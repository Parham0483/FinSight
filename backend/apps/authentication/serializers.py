from rest_framework import serializers
from django.contrib.auth import authenticate
from django.contrib.auth.password_validation import validate_password
from .models import User


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, validators=[validate_password])
    password_confirm = serializers.CharField(write_only=True)

    class Meta:
        model = User
        fields = ('email', 'full_name', 'password', 'password_confirm')

    def validate(self, attrs: dict) -> dict:
        if attrs['password'] != attrs['password_confirm']:
            raise serializers.ValidationError({'password_confirm': 'Passwords do not match.'})
        return attrs

    def create(self, validated_data: dict) -> User:
        validated_data.pop('password_confirm')
        return User.objects.create_user(**validated_data)


class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)

    def validate(self, attrs: dict) -> dict:
        user = authenticate(request=self.context.get('request'), username=attrs['email'], password=attrs['password'])
        if not user:
            raise serializers.ValidationError({'detail': 'Invalid email or password.'})
        if not user.is_verified:
            raise serializers.ValidationError({'detail': 'Please verify your email before logging in.'})
        attrs['user'] = user
        return attrs


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ('id', 'email', 'full_name', 'is_verified', 'created_at')
        read_only_fields = ('id', 'is_verified', 'created_at')


class EmailVerifySerializer(serializers.Serializer):
    token = serializers.CharField()
