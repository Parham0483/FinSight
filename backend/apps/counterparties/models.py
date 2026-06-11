import re
import uuid

from django.contrib.postgres.fields import ArrayField
from django.db import models

from apps.organisations.models import Organisation


def normalise_name(raw: str) -> str:
    """Collapse a counterparty descriptor to a comparable canonical key.

    Bank/accounting descriptors are noisy ("AMZN*MKTP UK*1A2B3", "AMAZON.CO.UK").
    We strip card-processor noise, punctuation, and case so that obvious
    variants resolve to the same key for auto-merge and dedup. This is a cheap
    deterministic pre-pass; the fuzzy matcher (§5) does the harder cases.
    """
    if not raw:
        return ''
    text = raw.lower()
    # Drop common card-network / processor prefixes and trailing reference ids.
    text = re.sub(r'\b(pos|crd|card|payment|pmt|ref|txn|visa|mastercard|paypal)\b', ' ', text)
    text = re.sub(r'[*#].*$', ' ', text)          # everything after a * or # is usually a ref
    text = re.sub(r'[^a-z0-9 ]+', ' ', text)       # punctuation → space
    text = re.sub(r'\b\d{4,}\b', ' ', text)        # long digit runs are reference numbers
    text = re.sub(r'\s+', ' ', text).strip()
    return text


class Counterparty(models.Model):
    """A party on the other side of a cash flow — the *who* behind a transaction.

    The blueprint (§5) unifies customers, suppliers, employees, lenders and tax
    authorities into one directory entity with a system ``type`` plus
    user-defined ``tags``. Type drives downstream behaviour (customers get
    payment-behaviour profiles and AR aging; suppliers get AP aging and
    recurring-obligation detection; employees feed payroll patterns).

    Entries are auto-created during ingestion and merged by the fuzzy matcher;
    every user correction (rename/retype/merge/tag) is auditable per §5.2.
    """

    TYPE_CUSTOMER = 'customer'
    TYPE_SUPPLIER = 'supplier'
    TYPE_EMPLOYEE = 'employee'
    TYPE_LENDER = 'lender'
    TYPE_TAX_AUTHORITY = 'tax_authority'
    TYPE_OTHER = 'other'
    TYPE_CHOICES = [
        (TYPE_CUSTOMER, 'Customer'),
        (TYPE_SUPPLIER, 'Supplier'),
        (TYPE_EMPLOYEE, 'Employee'),
        (TYPE_LENDER, 'Lender'),
        (TYPE_TAX_AUTHORITY, 'Tax Authority'),
        (TYPE_OTHER, 'Other'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    org = models.ForeignKey(Organisation, on_delete=models.CASCADE, related_name='counterparties')
    name = models.CharField(max_length=255)
    # Canonical key used for auto-merge and cross-source dedup. Indexed, not unique:
    # two genuinely different parties can normalise to the same key and a user
    # may keep them separate.
    normalised_name = models.CharField(max_length=255, db_index=True, blank=True)
    type = models.CharField(max_length=20, choices=TYPE_CHOICES, default=TYPE_OTHER)
    # User-defined groups on top of the system type ("wholesale clients", "Dubai suppliers").
    tags = ArrayField(models.CharField(max_length=64), default=list, blank=True)
    # ISO 3166-1 alpha-2 — feeds footprint-driven regional calendar intelligence (§7.4).
    country_code = models.CharField(max_length=2, blank=True, default='')
    email = models.EmailField(blank=True)
    # True when created automatically from ingestion (vs. user-created). Drives the
    # "needs review" surface and lets the matcher merge auto entries freely.
    is_auto_created = models.BooleanField(default=False)
    # When this party was merged into another, point at the survivor (soft-merge,
    # never destructive — §5.2 invariant 1).
    merged_into = models.ForeignKey(
        'self', on_delete=models.SET_NULL, null=True, blank=True, related_name='merged_from'
    )
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'counterparties'
        ordering = ('name',)
        indexes = [
            models.Index(fields=['org', 'type']),
            models.Index(fields=['org', 'normalised_name']),
        ]
        verbose_name_plural = 'counterparties'

    def __str__(self) -> str:
        return f'{self.name} ({self.get_type_display()})'

    @property
    def is_merged(self) -> bool:
        return self.merged_into_id is not None

    def save(self, *args, **kwargs) -> None:
        if not self.normalised_name:
            self.normalised_name = normalise_name(self.name)
        super().save(*args, **kwargs)
