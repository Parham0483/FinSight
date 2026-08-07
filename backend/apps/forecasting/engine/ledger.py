"""Layer 1 deterministic ledger — projects known cash flows, no statistics involved.

Combines three sources into one ordered sequence of `LedgerEntry`:
  - open AR (`counterparties.Invoice`, due_date in range)
  - open AP (`Bill`, due_date in range)
  - active `RecurringObligation` rows, expanded into individual occurrence dates

Money stays `Decimal` throughout and entries carry their original currency — this layer
does not convert to base currency; that is a concern for whoever consumes the ledger
(never discard the original amount/currency, per the money-handling rules).
"""

from __future__ import annotations

import calendar
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from typing import Literal

from apps.counterparties.models import Invoice
from apps.organisations.models import Organisation

from .models import Bill, RecurringObligation

SourceType = Literal['ar_invoice', 'ap_bill', 'recurring_obligation']

_OPEN_STATUSES = ('unpaid', 'partial', 'overdue')


@dataclass(frozen=True)
class LedgerEntry:
    """One known cash-flow event on a specific date. Amount is signed: positive = inflow."""

    date: date
    amount: Decimal
    currency: str
    source_type: SourceType
    source_id: str
    counterparty_id: str | None
    description: str


def _add_months(year: int, month: int, months: int) -> tuple[int, int]:
    total = (month - 1) + months
    return year + total // 12, total % 12 + 1


def _clamp_to_month(year: int, month: int, day: int) -> date:
    """Clamp an anchor day-of-month to that month's real last day (e.g. 31 -> 28/29/30)."""
    last_day = calendar.monthrange(year, month)[1]
    return date(year, month, min(day, last_day))


def _expand_weekly(obligation: RecurringObligation, start: date, end: date) -> list[LedgerEntry]:
    step_days = 14 if obligation.frequency == RecurringObligation.FREQUENCY_BIWEEKLY else 7
    cursor = obligation.start_date + timedelta(
        days=(obligation.anchor_weekday - obligation.start_date.weekday()) % 7
    )
    window_end = min(end, obligation.end_date) if obligation.end_date else end
    while cursor < start:
        cursor += timedelta(days=step_days)
    entries = []
    while cursor <= window_end:
        entries.append(_entry_for(obligation, cursor))
        cursor += timedelta(days=step_days)
    return entries


def _expand_monthly(obligation: RecurringObligation, start: date, end: date) -> list[LedgerEntry]:
    step_months = 3 if obligation.frequency == RecurringObligation.FREQUENCY_QUARTERLY else 1
    window_end = min(end, obligation.end_date) if obligation.end_date else end
    year, month = obligation.start_date.year, obligation.start_date.month
    entries = []
    while True:
        occurrence = _clamp_to_month(year, month, obligation.anchor_day)
        if occurrence > window_end:
            break
        if occurrence >= start and occurrence >= obligation.start_date:
            entries.append(_entry_for(obligation, occurrence))
        year, month = _add_months(year, month, step_months)
    return entries


def _expand_recurring(obligation: RecurringObligation, start: date, end: date) -> list[LedgerEntry]:
    window_start = max(start, obligation.start_date)
    window_end = min(end, obligation.end_date) if obligation.end_date else end
    if window_start > window_end:
        return []

    if obligation.frequency in (RecurringObligation.FREQUENCY_WEEKLY, RecurringObligation.FREQUENCY_BIWEEKLY):
        return _expand_weekly(obligation, start, end)
    return _expand_monthly(obligation, start, end)


def _entry_for(obligation: RecurringObligation, occurrence: date) -> LedgerEntry:
    return LedgerEntry(
        date=occurrence,
        amount=obligation.amount,
        currency=obligation.currency,
        source_type='recurring_obligation',
        source_id=str(obligation.id),
        counterparty_id=str(obligation.counterparty_id) if obligation.counterparty_id else None,
        description=obligation.description or obligation.get_kind_display(),
    )


def build_ledger(org: Organisation, start: date, end: date) -> tuple[LedgerEntry, ...]:
    """Project all known Layer 1 cash flows for `org` between `start` and `end` (inclusive)."""
    if end < start:
        raise ValueError('end date must not be before start date')

    entries: list[LedgerEntry] = []

    invoices = Invoice.objects.filter(
        org=org, status__in=_OPEN_STATUSES, due_date__gte=start, due_date__lte=end,
    )
    for invoice in invoices:
        entries.append(LedgerEntry(
            date=invoice.due_date,
            amount=abs(invoice.amount),
            currency=invoice.currency,
            source_type='ar_invoice',
            source_id=str(invoice.id),
            counterparty_id=str(invoice.counterparty_id) if invoice.counterparty_id else None,
            description=invoice.reference or f'Invoice {invoice.id}',
        ))

    bills = Bill.objects.filter(
        org=org, status__in=_OPEN_STATUSES, due_date__gte=start, due_date__lte=end,
    )
    for bill in bills:
        entries.append(LedgerEntry(
            date=bill.due_date,
            amount=-abs(bill.amount),
            currency=bill.currency,
            source_type='ap_bill',
            source_id=str(bill.id),
            counterparty_id=str(bill.counterparty_id) if bill.counterparty_id else None,
            description=bill.reference or f'Bill {bill.id}',
        ))

    obligations = RecurringObligation.objects.filter(org=org, is_active=True)
    for obligation in obligations:
        entries.extend(_expand_recurring(obligation, start, end))

    entries.sort(key=lambda e: (e.date, e.source_type, e.source_id))
    return tuple(entries)
