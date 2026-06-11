"""CSV bank-statement import.

The blueprint (§5) ships CSV import *before* bank-integration polish — it is
the fastest path to real data and the demo backbone. Banks export wildly
different column layouts, so this adapter takes a ``column_map`` (or a named
preset) describing which CSV headers map to our normalised fields, plus a
couple of presets for common UK/US layouts.

Amount handling supports the two conventions banks use:
  * a single signed ``amount`` column, or
  * separate ``debit``/``credit`` columns (debit → outflow, credit → inflow).
"""
from __future__ import annotations

import csv
import io
from datetime import datetime, time, timezone
from decimal import Decimal, InvalidOperation
from typing import Any, Iterable

from django.utils.dateparse import parse_date, parse_datetime

from .base import IngestionSource, NormalizedTransaction
from ..models import Transaction


# Named presets: friendly preset name → column_map. Users can also pass a raw
# column_map for any layout we don't have a preset for.
CSV_PRESETS: dict[str, dict[str, str]] = {
    'generic_signed': {
        'date': 'date',
        'description': 'description',
        'amount': 'amount',
        'currency': 'currency',
    },
    'generic_debit_credit': {
        'date': 'date',
        'description': 'description',
        'debit': 'debit',
        'credit': 'credit',
    },
    'starling': {
        'date': 'Date',
        'description': 'Reference',
        'counterparty': 'Counter Party',
        'amount': 'Amount (GBP)',
    },
    'wise': {
        'date': 'Date',
        'description': 'Description',
        'amount': 'Amount',
        'currency': 'Currency',
        'counterparty': 'Payee Name',
    },
}

_DATE_FORMATS = ('%Y-%m-%d', '%d/%m/%Y', '%m/%d/%Y', '%d-%m-%Y', '%d %b %Y', '%d/%m/%y')


def _parse_date(value: str) -> datetime:
    value = (value or '').strip()
    if not value:
        raise ValueError('Missing date.')
    # Try ISO datetime, then ISO date, then common bank formats.
    dt = parse_datetime(value)
    if dt is not None:
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    d = parse_date(value)
    if d is not None:
        return datetime.combine(d, time.min, tzinfo=timezone.utc)
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(value, fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    raise ValueError(f'Unrecognised date format: {value!r}')


def _parse_decimal(value: str) -> Decimal:
    cleaned = (value or '').strip().replace(',', '').replace('£', '').replace('$', '').replace('€', '')
    if not cleaned:
        return Decimal('0')
    try:
        return Decimal(cleaned)
    except InvalidOperation as exc:
        raise ValueError(f'Invalid amount: {value!r}') from exc


class CsvImportSource(IngestionSource):
    source_type = Transaction.SOURCE_CSV_IMPORT
    default_confidence = Decimal('0.900')

    def __init__(
        self,
        org,
        *,
        content: str,
        preset: str | None = None,
        column_map: dict[str, str] | None = None,
    ) -> None:
        super().__init__(org)
        self._content = content
        if column_map is not None:
            self.column_map = column_map
        elif preset is not None:
            if preset not in CSV_PRESETS:
                raise ValueError(f'Unknown CSV preset: {preset!r}. Known: {", ".join(sorted(CSV_PRESETS))}.')
            self.column_map = CSV_PRESETS[preset]
        else:
            self.column_map = CSV_PRESETS['generic_signed']

    def connect(self) -> None:
        return None

    def fetch(self) -> Iterable[Any]:
        reader = csv.DictReader(io.StringIO(self._content))
        if reader.fieldnames is None:
            raise ValueError('CSV has no header row.')
        # Validate the date column up front so we fail fast on a wrong preset.
        date_col = self.column_map.get('date')
        if date_col and date_col not in reader.fieldnames:
            raise ValueError(
                f'CSV is missing the "{date_col}" column expected by this mapping. '
                f'Found columns: {", ".join(reader.fieldnames)}.'
            )
        return list(reader)

    def _resolve_amount(self, row: dict) -> Decimal:
        cm = self.column_map
        if 'amount' in cm:
            return _parse_decimal(row.get(cm['amount'], ''))
        # debit/credit layout: credit is an inflow (+), debit an outflow (−).
        debit = _parse_decimal(row.get(cm.get('debit', ''), '')) if 'debit' in cm else Decimal('0')
        credit = _parse_decimal(row.get(cm.get('credit', ''), '')) if 'credit' in cm else Decimal('0')
        return credit - debit

    def normalise(self, raw: dict) -> NormalizedTransaction:
        cm = self.column_map
        timestamp = _parse_date(raw.get(cm.get('date', 'date'), ''))
        amount = self._resolve_amount(raw)
        currency = (raw.get(cm.get('currency', ''), '') or self.org.base_currency).strip().upper()

        return NormalizedTransaction(
            timestamp=timestamp,
            amount=amount,
            currency=currency,
            description=raw.get(cm.get('description', ''), '').strip(),
            counterparty_name=raw.get(cm.get('counterparty', ''), '').strip(),
            merchant_name=raw.get(cm.get('merchant', ''), '').strip(),
            confidence=self.default_confidence,
            raw={'csv_row': raw},
        )
