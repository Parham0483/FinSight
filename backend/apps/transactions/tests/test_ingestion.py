"""Tests for the IngestionSource contract and its concrete adapters."""
from datetime import datetime, timezone as dt_timezone
from decimal import Decimal
from typing import Any, Iterable

import pytest

from apps.categories.seeds import seed_default_categories
from apps.counterparties.models import Counterparty
from apps.transactions.ingestion import (
    CsvImportSource,
    IngestionResult,
    ManualEntrySource,
    NormalizedTransaction,
)
from apps.transactions.ingestion.base import IngestionSource
from apps.transactions.models import Transaction


# ── A tiny in-memory source to exercise the shared base pipeline directly ────
class _ListSource(IngestionSource):
    source_type = Transaction.SOURCE_BANK_FEED

    def __init__(self, org, items: list[NormalizedTransaction]) -> None:
        super().__init__(org)
        self._items = items

    def connect(self) -> None:
        return None

    def fetch(self) -> Iterable[Any]:
        return list(self._items)

    def normalise(self, raw: Any) -> NormalizedTransaction:
        return raw


def _norm(**kw) -> NormalizedTransaction:
    base = dict(
        timestamp=datetime(2026, 1, 1, 10, tzinfo=dt_timezone.utc),
        amount=Decimal('100.00'),
        currency='GBP',
    )
    base.update(kw)
    return NormalizedTransaction(**base)


@pytest.mark.django_db
class TestManualEntrySource:
    def test_creates_transaction_and_counterparty(self, org):
        result = ManualEntrySource(org, entries=[{
            'timestamp': '2026-01-01T10:00:00Z', 'amount': '250.00',
            'currency': 'GBP', 'counterparty_name': 'Acme Ltd',
            'counterparty_type': Counterparty.TYPE_CUSTOMER,
        }]).sync()

        assert result.created == 1
        txn = Transaction.objects.get(org=org)
        assert txn.amount == Decimal('250.00')
        assert txn.source == Transaction.SOURCE_MANUAL
        assert txn.counterparty.name == 'Acme Ltd'
        assert txn.counterparty.type == Counterparty.TYPE_CUSTOMER

    def test_links_category_by_slug(self, org):
        seed_default_categories(org)
        result = ManualEntrySource(org, entries=[{
            'timestamp': '2026-01-01T10:00:00Z', 'amount': '90.00',
            'currency': 'GBP', 'category_slug': 'customer_receipt',
        }]).sync()
        assert result.created == 1
        assert Transaction.objects.get(org=org).category.slug == 'customer_receipt'

    def test_auto_categorises_when_source_gives_no_category_slug(self, org):
        seed_default_categories(org)
        result = ManualEntrySource(org, entries=[{
            'timestamp': '2026-01-01T10:00:00Z', 'amount': '-500.00',
            'currency': 'GBP', 'description': 'HMRC VAT payment',
        }]).sync()
        assert result.created == 1
        txn = Transaction.objects.get(org=org)
        assert txn.category.slug == 'tax'
        assert txn.category_overridden is False  # a machine guess, not a human correction

    def test_blank_counterparty_leaves_link_null(self, org):
        ManualEntrySource(org, entries=[{
            'timestamp': '2026-01-01T10:00:00Z', 'amount': '5.00', 'currency': 'GBP',
        }]).sync()
        assert Transaction.objects.get(org=org).counterparty is None

    def test_bad_timestamp_is_a_row_error_not_a_crash(self, org):
        result = ManualEntrySource(org, entries=[{
            'timestamp': 'not-a-date', 'amount': '5.00', 'currency': 'GBP',
        }]).sync()
        assert result.created == 0
        assert len(result.errors) == 1

    def test_missing_amount_is_a_row_error(self, org):
        result = ManualEntrySource(org, entries=[{
            'timestamp': '2026-01-01T10:00:00Z', 'currency': 'GBP',
        }]).sync()
        assert result.created == 0
        assert len(result.errors) == 1


@pytest.mark.django_db
class TestCsvImportSource:
    def test_generic_signed(self, org):
        content = (
            'date,description,amount,currency\n'
            '2026-01-01,Coffee beans,-50.00,GBP\n'
            '2026-01-02,Client payment,500.00,GBP\n'
        )
        result = CsvImportSource(org, content=content, preset='generic_signed').sync()
        assert result.created == 2
        amounts = set(Transaction.objects.filter(org=org).values_list('amount', flat=True))
        assert amounts == {Decimal('-50.00'), Decimal('500.00')}

    def test_debit_credit_layout(self, org):
        content = (
            'date,description,debit,credit\n'
            '2026-01-01,Rent,2200.00,\n'
            '2026-01-02,Sale,,500.00\n'
        )
        result = CsvImportSource(org, content=content, preset='generic_debit_credit').sync()
        assert result.created == 2
        amounts = set(Transaction.objects.filter(org=org).values_list('amount', flat=True))
        assert amounts == {Decimal('-2200.00'), Decimal('500.00')}

    def test_starling_preset_resolves_counterparty(self, org):
        content = (
            'Date,Reference,Counter Party,Amount (GBP)\n'
            '2026-01-01,Invoice 12,Globex Corp,1200.00\n'
        )
        result = CsvImportSource(org, content=content, preset='starling').sync()
        assert result.created == 1
        assert Transaction.objects.get(org=org).counterparty.name == 'Globex Corp'

    def test_custom_column_map(self, org):
        content = 'when,memo,value\n2026-03-03,Stuff,12.50\n'
        column_map = {'date': 'when', 'description': 'memo', 'amount': 'value'}
        result = CsvImportSource(org, content=content, column_map=column_map).sync()
        assert result.created == 1
        assert Transaction.objects.get(org=org).amount == Decimal('12.50')

    def test_csv_confidence_below_one(self, org):
        content = 'date,description,amount,currency\n2026-01-01,X,1.00,GBP\n'
        CsvImportSource(org, content=content, preset='generic_signed').sync()
        assert Transaction.objects.get(org=org).confidence == Decimal('0.900')

    def test_unknown_preset_raises(self, org):
        with pytest.raises(ValueError, match='Unknown CSV preset'):
            CsvImportSource(org, content='x', preset='nope')

    def test_missing_date_column_raises_on_sync(self, org):
        content = 'wrong,header\n1,2\n'
        with pytest.raises(ValueError, match='missing the "date" column'):
            CsvImportSource(org, content=content, preset='generic_signed').sync()


@pytest.mark.django_db
class TestBasePipelineDedupAndIdempotency:
    def test_idempotent_resync_on_external_id(self, org):
        items = [_norm(external_id='bank-1', merchant_name='Acme')]
        first = _ListSource(org, items).sync()
        second = _ListSource(org, items).sync()
        assert first.created == 1
        assert second.created == 0
        assert second.skipped_existing == 1
        assert Transaction.objects.filter(org=org).count() == 1

    def test_cross_source_dedup_skips_equal_or_more_reliable(self, org):
        # Two manual entries for the same movement: the second is skipped.
        entry = {
            'timestamp': '2026-01-01T10:00:00Z', 'amount': '100.00',
            'currency': 'GBP', 'counterparty_name': 'Acme',
        }
        ManualEntrySource(org, entries=[entry]).sync()
        second = ManualEntrySource(org, entries=[entry]).sync()
        assert second.created == 0
        assert second.skipped_duplicates == 1
        assert Transaction.objects.filter(org=org).count() == 1

    def test_more_reliable_source_is_not_blocked_by_weaker_duplicate(self, org):
        # A manual record exists; a bank feed of the same movement is more
        # reliable, so it is allowed to land alongside it.
        ManualEntrySource(org, entries=[{
            'timestamp': '2026-01-01T10:00:00Z', 'amount': '100.00',
            'currency': 'GBP', 'merchant_name': 'Acme',
        }]).sync()
        result = _ListSource(org, [_norm(merchant_name='Acme')]).sync()
        assert result.created == 1
        assert Transaction.objects.filter(org=org).count() == 2


def test_ingestion_result_accounting():
    result = IngestionResult(created=2, skipped_duplicates=1, skipped_existing=1, errors=['boom'])
    assert result.total_processed == 5
    assert result.as_dict()['created'] == 2
    assert result.as_dict()['total_processed'] == 5
