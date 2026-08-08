import re
import uuid

from django.contrib.postgres.fields import ArrayField
from django.db import models

from apps.organisations.models import Organisation


# Card-network / processor noise words that carry no identity of the party.
_PROCESSOR_STOP_WORDS = frozenset({
    'pos', 'crd', 'card', 'payment', 'pmt', 'ref', 'txn',
    'visa', 'mastercard', 'paypal',
})


def normalise_name(raw: str) -> str:
    """Collapse a counterparty descriptor to a comparable canonical key.

    Bank/accounting descriptors are noisy ("AMZN*MKTP UK*1A2B3", "AMAZON.CO.UK").
    We tokenise on non-alphanumerics (so ``*``, ``#`` and ``.`` are separators,
    not truncation points), then drop processor noise words and any token that
    contains a digit (reference ids like ``1A2B3`` / ``1234567``). This is a
    cheap deterministic pre-pass; the fuzzy matcher (§5) handles harder cases.
    """
    if not raw:
        return ''
    tokens = re.split(r'[^a-z0-9]+', raw.lower())
    kept = [
        token for token in tokens
        if token
        and token not in _PROCESSOR_STOP_WORDS
        and not any(char.isdigit() for char in token)
    ]
    return ' '.join(kept)


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


class Invoice(models.Model):
    """An AR invoice against a customer-type Counterparty.

    Relocated from the retired `customers` app once Counterparty absorbed
    Customer (see `customers` migrations 0002-0005 and `0002_invoice` here).
    Not enforced at the DB level, but `counterparty` is expected to have
    ``type == Counterparty.TYPE_CUSTOMER`` — Django can't express a FK
    constrained to another table's column value, so this is a code
    convention checked in `clean()`.
    """

    STATUS_CHOICES = [
        ('unpaid', 'Unpaid'),
        ('partial', 'Partially Paid'),
        ('paid', 'Paid'),
        ('overdue', 'Overdue'),
        ('written_off', 'Written Off'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    org = models.ForeignKey(Organisation, on_delete=models.CASCADE, related_name='invoices')
    counterparty = models.ForeignKey(
        Counterparty, on_delete=models.SET_NULL, null=True, blank=True, related_name='invoices'
    )
    reference = models.CharField(max_length=100, blank=True)
    amount = models.DecimalField(max_digits=15, decimal_places=2)
    currency = models.CharField(max_length=3, default='GBP')
    issue_date = models.DateField()
    due_date = models.DateField()
    paid_date = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=50, choices=STATUS_CHOICES, default='unpaid')
    matched_transaction = models.ForeignKey(
        'transactions.Transaction', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='matched_invoices'
    )
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'invoices'
        indexes = [
            models.Index(fields=['status', 'due_date'], name='invoices_status_73cf28_idx'),
            models.Index(fields=['counterparty'], name='invoices_counterparty_idx'),
        ]

    def __str__(self) -> str:
        return f'{self.reference or self.id} — {self.counterparty} £{self.amount}'

    def clean(self):
        from django.core.exceptions import ValidationError
        if self.counterparty_id and self.counterparty.type != Counterparty.TYPE_CUSTOMER:
            raise ValidationError('Invoice.counterparty must be a customer-type Counterparty.')
