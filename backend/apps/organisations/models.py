import uuid
from django.db import models
from apps.authentication.models import User


class Organisation(models.Model):
    INDUSTRY_CHOICES = [
        ('import_export', 'Import / Export'),
        ('wholesale', 'Wholesale'),
        ('retail', 'Retail'),
        ('manufacturing', 'Manufacturing'),
        ('construction', 'Construction'),
        ('hospitality', 'Hospitality / Food & Beverage'),
        ('technology', 'Technology / SaaS'),
        ('professional_services', 'Professional Services'),
        ('logistics', 'Logistics / Transport'),
        ('agriculture', 'Agriculture'),
        ('healthcare', 'Healthcare'),
        ('education', 'Education'),
        ('services', 'Other Services'),
        ('other', 'Other'),
    ]

    # ISO 3166-1 alpha-2 country codes (stored, not constrained — future-proof)
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)
    industry = models.CharField(max_length=100, choices=INDUSTRY_CHOICES, default='other')
    country_code = models.CharField(max_length=2, default='', blank=True,
                                    help_text='ISO 3166-1 alpha-2, e.g. GB, US, AE, TR')
    base_currency = models.CharField(max_length=3, default='USD',
                                     help_text='ISO 4217 currency code')
    timezone = models.CharField(max_length=100, default='UTC')
    locale = models.CharField(max_length=10, default='en',
                              help_text='BCP 47 locale for number/date formatting, e.g. en-GB, ar-AE')
    is_demo = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'organisations'

    def __str__(self) -> str:
        return f'{self.name} ({self.country_code or "—"})'


class OrgMembership(models.Model):
    ROLE_CHOICES = [
        ('owner', 'Owner'),
        ('admin', 'Admin'),
        ('viewer', 'Viewer'),
        ('accountant', 'Accountant (external)'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='memberships')
    org = models.ForeignKey(Organisation, on_delete=models.CASCADE, related_name='memberships')
    role = models.CharField(max_length=50, choices=ROLE_CHOICES, default='owner')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'org_memberships'
        unique_together = ('user', 'org')

    def __str__(self) -> str:
        return f'{self.user.email} → {self.org.name} ({self.role})'
