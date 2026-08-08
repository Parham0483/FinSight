"""Layer 1 — deterministic ledger of known cash flows (blueprint §3 Layer 1, §8 Phase 2).

Two new obligation types sit alongside the existing `counterparties.Invoice` (AR):

- `Bill`: the AP counterpart — supplier bills with due dates. Mirrors `Invoice`'s shape
  rather than generalising that model, because `counterparties/` is owned by Phase 1 and
  this phase does not edit other phases' files.
- `RecurringObligation`: payroll/rent/loan and other cadence-driven flows that aren't
  invoice-shaped at all — a fixed amount recurring on a schedule, not tied to a single
  due-dated document. Phase 4's recurring-transaction detection will later promote
  detected patterns into these (`source=SOURCE_DETECTED`); Phase 2 only needs the
  manually-entered case (`source=SOURCE_MANUAL`).

These live under `forecasting.engine` for file organisation but register under the
`forecasting` app label — see the imports at the bottom of `forecasting/models.py`.
"""

import uuid

from django.core.exceptions import ValidationError
from django.db import models

from apps.counterparties.models import Counterparty
from apps.organisations.models import Organisation


class Bill(models.Model):
    """An AP bill from a supplier-type Counterparty — the AP counterpart to `counterparties.Invoice`."""

    STATUS_CHOICES = [
        ('unpaid', 'Unpaid'),
        ('partial', 'Partially Paid'),
        ('paid', 'Paid'),
        ('overdue', 'Overdue'),
        ('written_off', 'Written Off'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    org = models.ForeignKey(Organisation, on_delete=models.CASCADE, related_name='bills')
    counterparty = models.ForeignKey(
        Counterparty, on_delete=models.SET_NULL, null=True, blank=True, related_name='bills',
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
        null=True, blank=True, related_name='matched_bills',
    )
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'forecasting'
        db_table = 'bills'
        indexes = [
            models.Index(fields=['status', 'due_date'], name='bills_status_due_idx'),
            models.Index(fields=['counterparty'], name='bills_counterparty_idx'),
        ]

    def __str__(self) -> str:
        return f'{self.reference or self.id} — {self.counterparty} {self.currency}{self.amount}'

    def clean(self):
        if self.counterparty_id and self.counterparty.type != Counterparty.TYPE_SUPPLIER:
            raise ValidationError('Bill.counterparty must be a supplier-type Counterparty.')


class RecurringObligation(models.Model):
    """A scheduled cash flow that recurs on a cadence rather than being tied to one document.

    Covers payroll, rent/lease, and loan repayments per blueprint §3 Layer 1.
    """

    KIND_PAYROLL = 'payroll'
    KIND_RENT = 'rent'
    KIND_LOAN = 'loan'
    KIND_OTHER = 'other'
    KIND_CHOICES = [
        (KIND_PAYROLL, 'Payroll'),
        (KIND_RENT, 'Rent / Lease'),
        (KIND_LOAN, 'Loan Repayment'),
        (KIND_OTHER, 'Other Recurring'),
    ]

    FREQUENCY_WEEKLY = 'weekly'
    FREQUENCY_BIWEEKLY = 'biweekly'
    FREQUENCY_MONTHLY = 'monthly'
    FREQUENCY_QUARTERLY = 'quarterly'
    FREQUENCY_CHOICES = [
        (FREQUENCY_WEEKLY, 'Weekly'),
        (FREQUENCY_BIWEEKLY, 'Every 2 Weeks'),
        (FREQUENCY_MONTHLY, 'Monthly'),
        (FREQUENCY_QUARTERLY, 'Quarterly'),
    ]

    SOURCE_MANUAL = 'manual'
    SOURCE_DETECTED = 'detected'
    SOURCE_CHOICES = [
        (SOURCE_MANUAL, 'Manually Entered'),
        (SOURCE_DETECTED, 'Detected (Phase 4)'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    org = models.ForeignKey(Organisation, on_delete=models.CASCADE, related_name='recurring_obligations')
    counterparty = models.ForeignKey(
        Counterparty, on_delete=models.SET_NULL, null=True, blank=True, related_name='recurring_obligations',
    )
    kind = models.CharField(max_length=20, choices=KIND_CHOICES, default=KIND_OTHER)
    description = models.CharField(max_length=255, blank=True)
    # Signed: positive = inflow, negative = outflow (matches transactions.Transaction convention).
    amount = models.DecimalField(max_digits=15, decimal_places=2)
    currency = models.CharField(max_length=3, default='GBP')
    frequency = models.CharField(max_length=20, choices=FREQUENCY_CHOICES, default=FREQUENCY_MONTHLY)
    # Day-of-month anchor for monthly/quarterly (1-31, clamped to the month's real length);
    # required for those frequencies, ignored otherwise.
    anchor_day = models.PositiveSmallIntegerField(null=True, blank=True)
    # Weekday anchor for weekly/biweekly (0=Monday .. 6=Sunday); required for those
    # frequencies, ignored otherwise.
    anchor_weekday = models.PositiveSmallIntegerField(null=True, blank=True)
    start_date = models.DateField()
    end_date = models.DateField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    source = models.CharField(max_length=20, choices=SOURCE_CHOICES, default=SOURCE_MANUAL)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'forecasting'
        db_table = 'recurring_obligations'
        indexes = [
            models.Index(fields=['org', 'is_active'], name='recurobl_org_active_idx'),
        ]

    def __str__(self) -> str:
        return f'{self.get_kind_display()} {self.currency}{self.amount} ({self.get_frequency_display()})'

    def clean(self):
        if self.frequency in (self.FREQUENCY_WEEKLY, self.FREQUENCY_BIWEEKLY) and self.anchor_weekday is None:
            raise ValidationError('anchor_weekday is required for weekly/biweekly frequency.')
        if self.frequency in (self.FREQUENCY_MONTHLY, self.FREQUENCY_QUARTERLY) and self.anchor_day is None:
            raise ValidationError('anchor_day is required for monthly/quarterly frequency.')
        if self.end_date and self.end_date < self.start_date:
            raise ValidationError('end_date cannot be before start_date.')
