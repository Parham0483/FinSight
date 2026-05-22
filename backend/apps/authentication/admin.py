from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import EmailVerificationToken, User


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ('email', 'full_name', 'is_verified', 'is_staff', 'created_at')
    list_filter = ('is_verified', 'is_staff', 'is_superuser')
    search_fields = ('email', 'full_name')
    ordering = ('-created_at',)
    fieldsets = (
        (None, {'fields': ('email', 'password')}),
        ('Personal', {'fields': ('full_name',)}),
        ('Status', {'fields': ('is_verified', 'is_active', 'is_staff', 'is_superuser')}),
        ('Permissions', {'fields': ('groups', 'user_permissions')}),
    )
    add_fieldsets = (
        (None, {'classes': ('wide',), 'fields': ('email', 'full_name', 'password1', 'password2')}),
    )


@admin.register(EmailVerificationToken)
class EmailVerificationTokenAdmin(admin.ModelAdmin):
    list_display = ('user', 'used', 'expires_at', 'created_at')
    list_filter = ('used',)
    search_fields = ('user__email',)
