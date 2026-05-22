import uuid
from django.db import models
from apps.authentication.models import User


class Organisation(models.Model):
    INDUSTRY_CHOICES = [
        ('import_export', 'Import / Export'),
        ('wholesale', 'Wholesale'),
        ('retail', 'Retail'),
        ('manufacturing', 'Manufacturing'),
        ('services', 'Services'),
        ('other', 'Other'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)
    industry = models.CharField(max_length=100, choices=INDUSTRY_CHOICES, default='other')
    base_currency = models.CharField(max_length=3, default='GBP')
    timezone = models.CharField(max_length=100, default='Europe/London')
    is_demo = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'organisations'

    def __str__(self) -> str:
        return self.name


class OrgMembership(models.Model):
    ROLE_CHOICES = [
        ('owner', 'Owner'),
        ('admin', 'Admin'),
        ('viewer', 'Viewer'),
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
