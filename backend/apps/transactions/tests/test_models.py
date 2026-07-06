"""Unit tests for the source-agnostic Transaction model."""
from decimal import Decimal

import pytest
from django.db import IntegrityError, transaction as db_transaction
from django.utils import timezone

from apps.counterparties.models import Counterparty
from apps.transactions.models import Transaction


def _make(org, **overrides) -> Transaction:
    defaults = dict(
        org=org,
        timestamp=timezone.now(),
        amount=Decimal('100.00'),
        currency='GBP',
    )
    defaults.update(overrides)
    return Transaction.objects.create(**defaults)


@pytest.mark.django_db
class TestTransactionModel:
    def test_direction_inflow_and_outflow(self, org):
        assert _make(org, amount=Decimal('10.00')).direction == 'inflow'
        assert _make(org, amount=Decimal('-10.00')).direction == 'outflow'
        # Zero is treated as an inflow (>= 0) per the model's convention.
        assert _make(org, amount=Decimal('0.00')).direction == 'inflow'

    def test_source_reliability_ranking(self, org):
        bank = _make(org, source=Transaction.SOURCE_BANK_FEED)
        manual = _make(org, source=Transaction.SOURCE_MANUAL)
        assert bank.source_reliability > manual.source_reliability

    def test_save_populates_dedup_hash(self, org):
        txn = _make(org, merchant_name='Tesco')
        assert txn.dedup_hash != ''
        assert len(txn.dedup_hash) == 64  # sha256 hex

    def test_dedup_hash_stable_for_same_movement(self, org):
        ts = timezone.now()
        a = _make(org, timestamp=ts, amount=Decimal('42.00'), currency='GBP', merchant_name='Acme')
        b = _make(org, timestamp=ts, amount=Decimal('42.00'), currency='GBP', merchant_name='Acme')
        assert a.dedup_hash == b.dedup_hash

    def test_dedup_hash_differs_on_amount(self, org):
        ts = timezone.now()
        a = _make(org, timestamp=ts, amount=Decimal('42.00'), merchant_name='Acme')
        b = _make(org, timestamp=ts, amount=Decimal('43.00'), merchant_name='Acme')
        assert a.dedup_hash != b.dedup_hash

    def test_dedup_hash_uses_counterparty_key(self, org):
        cp = Counterparty.objects.create(org=org, name='Acme Ltd')
        ts = timezone.now()
        with_cp = _make(org, timestamp=ts, amount=Decimal('5.00'), counterparty=cp)
        with_name = _make(org, timestamp=ts, amount=Decimal('5.00'), merchant_name='Acme Ltd')
        # Counterparty normalised_name ('acme ltd') != raw merchant_name ('Acme Ltd'
        # lowercased is 'acme ltd') — both lowercase to the same basis here.
        assert with_cp.dedup_hash == with_name.dedup_hash

    def test_unique_external_id_per_org_source(self, org):
        ts = timezone.now()
        _make(org, source=Transaction.SOURCE_BANK_FEED, external_id='ext-1', timestamp=ts)
        with pytest.raises(IntegrityError):
            with db_transaction.atomic():
                _make(org, source=Transaction.SOURCE_BANK_FEED, external_id='ext-1', timestamp=ts,
                      amount=Decimal('999.00'))

    def test_null_external_ids_do_not_collide(self, org):
        # The unique constraint is conditional on external_id NOT NULL, so many
        # null-external_id rows must coexist.
        _make(org, external_id=None, amount=Decimal('1.00'))
        _make(org, external_id=None, amount=Decimal('2.00'))
        assert Transaction.objects.filter(org=org).count() == 2

    def test_str_shows_direction(self, org):
        assert _make(org, amount=Decimal('5.00'), description='Coffee').__str__().startswith('IN')
        assert _make(org, amount=Decimal('-5.00'), description='Rent').__str__().startswith('OUT')
