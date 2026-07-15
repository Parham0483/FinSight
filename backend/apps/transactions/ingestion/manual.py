"""Manual-entry ingestion source.

The simplest adapter: the caller already hands us normalised dicts (from a form
or the API), so ``fetch`` just replays them and ``normalise`` validates types.
Demonstrates that even hand-entered data flows through the same pipeline as a
bank feed — the whole point of the §5 adapter contract.
"""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Any, Iterable

from django.utils.dateparse import parse_datetime

from apps.counterparties.models import Counterparty

from .base import IngestionSource, NormalizedTransaction
from ..models import Transaction


class ManualEntrySource(IngestionSource):
    source_type = Transaction.SOURCE_MANUAL
    default_confidence = Decimal('1.000')

    def __init__(self, org, entries: list[dict]) -> None:
        super().__init__(org)
        self._entries = entries

    def connect(self) -> None:  # nothing to connect to
        return None

    def fetch(self) -> Iterable[Any]:
        return list(self._entries)

    def normalise(self, raw: dict) -> NormalizedTransaction:
        timestamp = raw.get('timestamp')
        if isinstance(timestamp, str):
            parsed = parse_datetime(timestamp)
            if parsed is None:
                raise ValueError(f'Unparseable timestamp: {timestamp!r}')
            timestamp = parsed
        if not isinstance(timestamp, datetime):
            raise ValueError('Manual entry requires a datetime "timestamp".')

        try:
            amount = Decimal(str(raw['amount']))
        except (KeyError, InvalidOperation) as exc:
            raise ValueError(f'Invalid or missing amount: {raw.get("amount")!r}') from exc

        return NormalizedTransaction(
            timestamp=timestamp,
            amount=amount,
            currency=(raw.get('currency') or self.org.base_currency).upper(),
            description=raw.get('description', ''),
            counterparty_name=raw.get('counterparty_name', ''),
            counterparty_type=raw.get('counterparty_type', Counterparty.TYPE_OTHER),
            merchant_name=raw.get('merchant_name', ''),
            category_slug=raw.get('category_slug'),
            confidence=Decimal('1.000'),
            raw={'manual': True},
        )
