import hashlib
import uuid
from decimal import Decimal

from django.contrib.postgres.fields import ArrayField
from django.db import models

from apps.banking.models import BankAccount
from apps.categories.models import Category
from apps.counterparties.models import Counterparty
from apps.organisations.models import Organisation


class Transaction(models.Model):
    """A single cash movement, normalised from any ingestion source.

    The blueprint (§5) requires one Transaction shape that every source —
    bank feeds, accounting APIs, documents, CSV, manual entry — normalises
    into, each carrying a ``source`` and ``confidence``. Money is stored in
    both its original currency and the org's base currency (converted at the
    transaction-date rate) so forecasting can run in one currency while the FX
    exposure report still sees the original.

    Sign convention: ``amount`` positive = inflow, negative = outflow.
    """

    SOURCE_BANK_FEED = 'bank_feed'
    SOURCE_ACCOUNTING_API = 'accounting_api'
    SOURCE_DOCUMENT = 'document'
    SOURCE_CSV_IMPORT = 'csv_import'
    SOURCE_MANUAL = 'manual'
    SOURCE_CHOICES = [
        (SOURCE_BANK_FEED, 'Bank Feed'),
        (SOURCE_ACCOUNTING_API, 'Accounting Platform'),
        (SOURCE_DOCUMENT, 'Document Extraction'),
        (SOURCE_CSV_IMPORT, 'CSV Import'),
        (SOURCE_MANUAL, 'Manual Entry'),
    ]

    # Source reliability ordering — used by maturity scoring and cross-source
    # dedup (a bank-feed record outranks a manual one for the same movement).
    SOURCE_RELIABILITY = {
        SOURCE_BANK_FEED: 100,
        SOURCE_ACCOUNTING_API: 90,
        SOURCE_DOCUMENT: 60,
        SOURCE_CSV_IMPORT: 50,
        SOURCE_MANUAL: 40,
    }

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    org = models.ForeignKey(Organisation, on_delete=models.CASCADE, related_name='transactions')
    # Only bank-feed transactions carry an account; other sources leave it null.
    account = models.ForeignKey(
        BankAccount, on_delete=models.CASCADE, related_name='transactions',
        null=True, blank=True,
    )
    source = models.CharField(max_length=20, choices=SOURCE_CHOICES, default=SOURCE_MANUAL)
    # The source's own id for this record (TrueLayer txn id, accounting line id,
    # document id…). Nullable; unique per (org, source) when present so a re-sync
    # is idempotent without colliding across sources.
    external_id = models.CharField(max_length=255, blank=True, null=True)
    # Extractor / matcher confidence in this record, 0–1. 1.0 for authoritative
    # sources (bank feed, manual); lower for document extraction.
    confidence = models.DecimalField(max_digits=4, decimal_places=3, default=Decimal('1.000'))

    timestamp = models.DateTimeField(db_index=True)
    description = models.TextField(blank=True)

    # Original-currency amount as it appears on the source.
    amount = models.DecimalField(max_digits=15, decimal_places=2)
    currency = models.CharField(max_length=3, default='USD')
    # Base-currency equivalent at the transaction-date rate (§5 multi-currency).
    base_amount = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
    base_currency = models.CharField(max_length=3, blank=True, default='')
    fx_rate = models.DecimalField(max_digits=18, decimal_places=8, null=True, blank=True)

    merchant_name = models.CharField(max_length=255, blank=True)
    counterparty = models.ForeignKey(
        Counterparty, on_delete=models.SET_NULL, null=True, blank=True, related_name='transactions',
    )
    # Canonical category link to the hierarchical taxonomy (categories app).
    category = models.ForeignKey(
        Category, on_delete=models.SET_NULL, null=True, blank=True, related_name='transactions',
    )
    category_overridden = models.BooleanField(default=False)

    is_recurring = models.BooleanField(default=False)
    recurring_group_id = models.UUIDField(null=True, blank=True, db_index=True)
    tags = ArrayField(models.CharField(max_length=100), default=list, blank=True)

    # Cross-source dedup key: hash of date + amount + counterparty key. Two
    # sources reporting the same movement collide here so we can keep the most
    # reliable one (§5 cross-source dedup).
    dedup_hash = models.CharField(max_length=64, blank=True, db_index=True)

    raw_data = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'transactions'
        ordering = ('-timestamp',)
        indexes = [
            models.Index(fields=['org', '-timestamp']),
            models.Index(fields=['org', 'source']),
            models.Index(fields=['account', '-timestamp']),
            models.Index(fields=['is_recurring', 'recurring_group_id']),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=['org', 'source', 'external_id'],
                condition=models.Q(external_id__isnull=False),
                name='uniq_external_id_per_org_source',
            ),
        ]

    def __str__(self) -> str:
        direction = 'IN' if self.amount > 0 else 'OUT'
        return f'{direction} {abs(self.amount)} {self.currency} — {self.description[:40]}'

    @property
    def direction(self) -> str:
        return 'inflow' if self.amount >= 0 else 'outflow'

    @property
    def source_reliability(self) -> int:
        return self.SOURCE_RELIABILITY.get(self.source, 0)

    def compute_dedup_hash(self) -> str:
        """Deterministic key for cross-source dedup: date + amount + party."""
        party = self.counterparty.normalised_name if self.counterparty_id else (self.merchant_name or '')
        day = self.timestamp.date().isoformat() if self.timestamp else ''
        basis = f'{day}|{self.amount}|{self.currency}|{party.lower().strip()}'
        return hashlib.sha256(basis.encode('utf-8')).hexdigest()

    def save(self, *args, **kwargs) -> None:
        if self.timestamp is not None:
            self.dedup_hash = self.compute_dedup_hash()
        super().save(*args, **kwargs)
