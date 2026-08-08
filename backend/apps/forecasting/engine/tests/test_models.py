"""Light smoke tests for Bill and RecurringObligation — standard CRUD models,
not money-critical logic themselves (the ledger expansion is tested separately
in test_ledger.py, which is where the risk-based testing bar actually applies).
"""
from datetime import date
from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError

from apps.counterparties.models import Counterparty
from apps.forecasting.engine.models import Bill, RecurringObligation

pytestmark = pytest.mark.unit


@pytest.fixture
def supplier(org) -> Counterparty:
    return Counterparty.objects.create(org=org, name='Acme Supplies Ltd', type=Counterparty.TYPE_SUPPLIER)


@pytest.fixture
def customer(org) -> Counterparty:
    return Counterparty.objects.create(org=org, name='Big Client Co', type=Counterparty.TYPE_CUSTOMER)


@pytest.mark.django_db
def test_bill_accepts_supplier_counterparty(org, supplier):
    bill = Bill.objects.create(
        org=org, counterparty=supplier, amount=Decimal('500.00'), currency='GBP',
        issue_date=date(2026, 7, 1), due_date=date(2026, 7, 31),
    )
    bill.full_clean()
    assert bill.status == 'unpaid'


@pytest.mark.django_db
def test_bill_rejects_customer_counterparty(org, customer):
    bill = Bill(
        org=org, counterparty=customer, amount=Decimal('500.00'), currency='GBP',
        issue_date=date(2026, 7, 1), due_date=date(2026, 7, 31),
    )
    with pytest.raises(ValidationError):
        bill.clean()


@pytest.mark.django_db
def test_recurring_obligation_monthly_requires_anchor_day(org):
    obligation = RecurringObligation(
        org=org, kind=RecurringObligation.KIND_RENT, amount=Decimal('-2000.00'),
        currency='GBP', frequency=RecurringObligation.FREQUENCY_MONTHLY,
        start_date=date(2026, 1, 1),
    )
    with pytest.raises(ValidationError):
        obligation.clean()


@pytest.mark.django_db
def test_recurring_obligation_weekly_requires_anchor_weekday(org):
    obligation = RecurringObligation(
        org=org, kind=RecurringObligation.KIND_PAYROLL, amount=Decimal('-1000.00'),
        currency='GBP', frequency=RecurringObligation.FREQUENCY_WEEKLY,
        start_date=date(2026, 1, 1),
    )
    with pytest.raises(ValidationError):
        obligation.clean()


@pytest.mark.django_db
def test_recurring_obligation_end_date_before_start_date_rejected(org):
    obligation = RecurringObligation(
        org=org, kind=RecurringObligation.KIND_LOAN, amount=Decimal('-500.00'),
        currency='GBP', frequency=RecurringObligation.FREQUENCY_MONTHLY,
        anchor_day=1, start_date=date(2026, 6, 1), end_date=date(2026, 1, 1),
    )
    with pytest.raises(ValidationError):
        obligation.clean()


@pytest.mark.django_db
def test_recurring_obligation_valid_monthly_saves(org):
    obligation = RecurringObligation.objects.create(
        org=org, kind=RecurringObligation.KIND_RENT, amount=Decimal('-2000.00'),
        currency='GBP', frequency=RecurringObligation.FREQUENCY_MONTHLY,
        anchor_day=1, start_date=date(2026, 1, 1),
    )
    obligation.full_clean()
    assert obligation.is_active is True
    assert obligation.source == RecurringObligation.SOURCE_MANUAL
