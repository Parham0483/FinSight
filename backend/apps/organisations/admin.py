from django.contrib import admin
from .models import Organisation, OrgMembership

@admin.register(Organisation)
class OrganisationAdmin(admin.ModelAdmin):
    list_display = ('name', 'industry', 'base_currency', 'is_demo', 'created_at')
    list_filter = ('industry', 'base_currency', 'is_demo')
    search_fields = ('name',)

@admin.register(OrgMembership)
class OrgMembershipAdmin(admin.ModelAdmin):
    list_display = ('user', 'org', 'role', 'created_at')
    list_filter = ('role',)
    search_fields = ('user__email', 'org__name')
