"""Layer 1 ledger — risk-based tests per the money-handling bar: this is the
deterministic cash-flow projection every later phase builds on, so sign
conventions, date-window boundaries, and recurring-schedule expansion all get
mandatory coverage rather than a light smoke test.
"""
from datetime import date
from decimal import Decimal

import pytest

from apps.counterparties.models import Counterparty, Invoice
from apps.forecasting.engine.ledger import build_ledger
from apps.forecasting.engine.models import Bill, RecurringObligation

pytestmark = pytest.mark.unit


@pytest.fixture
def customer(org) -> Counterparty:
    return Counterparty.objects.create(org=org, name='Big Client Co', type=Counterparty.TYPE_CUSTOMER)


@pytest.fixture
def supplier(org) -> Counterparty:
    return Counterparty.objects.create(org=org, name='Acme Supplies Ltd', type=Counterparty.TYPE_SUPPLIER)


@pytest.mark.django_db
def test_ar_invoice_in_range_is_positive_inflow(org, customer):
    Invoice.objects.create(
        org=org, counterparty=customer, amount=Decimal('1500.00'), currency='GBP',
        issue_date=date(2026, 7, 1), due_date=date(2026, 7, 15), status='unpaid',
    )
    entries = build_ledger(org, date(2026, 7, 1), date(2026, 7, 31))
    assert len(entries) == 1
    assert entries[0].source_type == 'ar_invoice'
    assert entries[0].amount == Decimal('1500.00')
    assert isinstance(entries[0].amount, Decimal)


@pytest.mark.django_db
def test_ap_bill_in_range_is_negative_outflow(org, supplier):
    Bill.objects.create(
        org=org, counterparty=supplier, amount=Decimal('600.00'), currency='GBP',
        issue_date=date(2026, 7, 1), due_date=date(2026, 7, 20), status='unpaid',
    )
    entries = build_ledger(org, date(2026, 7, 1), date(2026, 7, 31))
    assert len(entries) == 1
    assert entries[0].source_type == 'ap_bill'
    assert entries[0].amount == Decimal('-600.00')


@pytest.mark.django_db
def test_paid_invoices_and_bills_are_excluded(org, customer, supplier):
    Invoice.objects.create(
        org=org, counterparty=customer, amount=Decimal('100.00'), currency='GBP',
        issue_date=date(2026, 7, 1), due_date=date(2026, 7, 10), status='paid',
    )
    Bill.objects.create(
        org=org, counterparty=supplier, amount=Decimal('50.00'), currency='GBP',
        issue_date=date(2026, 7, 1), due_date=date(2026, 7, 10), status='written_off',
    )
    entries = build_ledger(org, date(2026, 7, 1), date(2026, 7, 31))
    assert entries == ()


@pytest.mark.django_db
def test_invoice_due_outside_window_is_excluded(org, customer):
    Invoice.objects.create(
        org=org, counterparty=customer, amount=Decimal('100.00'), currency='GBP',
        issue_date=date(2026, 7, 1), due_date=date(2026, 8, 5), status='unpaid',
    )
    entries = build_ledger(org, date(2026, 7, 1), date(2026, 7, 31))
    assert entries == ()


@pytest.mark.django_db
def test_monthly_recurring_obligation_clamps_short_month(org):
    """anchor_day=31 in February must land on the 28th (2026 is not a leap year), not raise."""
    RecurringObligation.objects.create(
        org=org, kind=RecurringObligation.KIND_RENT, amount=Decimal('-2000.00'),
        currency='GBP', frequency=RecurringObligation.FREQUENCY_MONTHLY,
        anchor_day=31, start_date=date(2026, 1, 1),
    )
    entries = build_ledger(org, date(2026, 2, 1), date(2026, 2, 28))
    assert len(entries) == 1
    assert entries[0].date == date(2026, 2, 28)
    assert entries[0].amount == Decimal('-2000.00')


@pytest.mark.django_db
def test_monthly_recurring_obligation_expands_across_multiple_months(org):
    RecurringObligation.objects.create(
        org=org, kind=RecurringObligation.KIND_RENT, amount=Decimal('-1800.00'),
        currency='GBP', frequency=RecurringObligation.FREQUENCY_MONTHLY,
        anchor_day=1, start_date=date(2026, 1, 1),
    )
    entries = build_ledger(org, date(2026, 1, 1), date(2026, 3, 31))
    dates = [e.date for e in entries]
    assert dates == [date(2026, 1, 1), date(2026, 2, 1), date(2026, 3, 1)]


@pytest.mark.django_db
def test_quarterly_recurring_obligation_steps_by_three_months(org):
    RecurringObligation.objects.create(
        org=org, kind=RecurringObligation.KIND_LOAN, amount=Decimal('-5000.00'),
        currency='GBP', frequency=RecurringObligation.FREQUENCY_QUARTERLY,
        anchor_day=15, start_date=date(2026, 1, 15),
    )
    entries = build_ledger(org, date(2026, 1, 1), date(2026, 12, 31))
    dates = [e.date for e in entries]
    assert dates == [date(2026, 1, 15), date(2026, 4, 15), date(2026, 7, 15), date(2026, 10, 15)]


@pytest.mark.django_db
def test_weekly_recurring_obligation_lands_on_anchor_weekday(org):
    # anchor_weekday=0 (Monday); start_date is a Wednesday (2026-07-01).
    RecurringObligation.objects.create(
        org=org, kind=RecurringObligation.KIND_PAYROLL, amount=Decimal('-3000.00'),
        currency='GBP', frequency=RecurringObligation.FREQUENCY_WEEKLY,
        anchor_weekday=0, start_date=date(2026, 7, 1),
    )
    entries = build_ledger(org, date(2026, 7, 1), date(2026, 7, 31))
    assert all(e.date.weekday() == 0 for e in entries)
    assert date(2026, 7, 6) in [e.date for e in entries]  # first Monday on/after start_date


@pytest.mark.django_db
def test_biweekly_recurring_obligation_steps_by_fourteen_days(org):
    RecurringObligation.objects.create(
        org=org, kind=RecurringObligation.KIND_PAYROLL, amount=Decimal('-3000.00'),
        currency='GBP', frequency=RecurringObligation.FREQUENCY_BIWEEKLY,
        anchor_weekday=4, start_date=date(2026, 7, 3),  # a Friday
    )
    entries = build_ledger(org, date(2026, 7, 1), date(2026, 8, 31))
    dates = [e.date for e in entries]
    for a, b in zip(dates, dates[1:]):
        assert (b - a).days == 14


@pytest.mark.django_db
def test_inactive_recurring_obligation_is_excluded(org):
    RecurringObligation.objects.create(
        org=org, kind=RecurringObligation.KIND_OTHER, amount=Decimal('-100.00'),
        currency='GBP', frequency=RecurringObligation.FREQUENCY_MONTHLY,
        anchor_day=1, start_date=date(2026, 1, 1), is_active=False,
    )
    entries = build_ledger(org, date(2026, 1, 1), date(2026, 12, 31))
    assert entries == ()


@pytest.mark.django_db
def test_recurring_obligation_respects_end_date(org):
    RecurringObligation.objects.create(
        org=org, kind=RecurringObligation.KIND_LOAN, amount=Decimal('-500.00'),
        currency='GBP', frequency=RecurringObligation.FREQUENCY_MONTHLY,
        anchor_day=1, start_date=date(2026, 1, 1), end_date=date(2026, 3, 1),
    )
    entries = build_ledger(org, date(2026, 1, 1), date(2026, 6, 30))
    dates = [e.date for e in entries]
    assert dates == [date(2026, 1, 1), date(2026, 2, 1), date(2026, 3, 1)]


@pytest.mark.django_db
def test_recurring_obligation_does_not_occur_before_start_date(org):
    RecurringObligation.objects.create(
        org=org, kind=RecurringObligation.KIND_RENT, amount=Decimal('-1000.00'),
        currency='GBP', frequency=RecurringObligation.FREQUENCY_MONTHLY,
        anchor_day=15, start_date=date(2026, 3, 15),
    )
    entries = build_ledger(org, date(2026, 1, 1), date(2026, 3, 31))
    dates = [e.date for e in entries]
    assert dates == [date(2026, 3, 15)]


@pytest.mark.django_db
def test_entries_are_sorted_by_date(org, customer, supplier):
    Invoice.objects.create(
        org=org, counterparty=customer, amount=Decimal('100.00'), currency='GBP',
        issue_date=date(2026, 7, 1), due_date=date(2026, 7, 25), status='unpaid',
    )
    Bill.objects.create(
        org=org, counterparty=supplier, amount=Decimal('50.00'), currency='GBP',
        issue_date=date(2026, 7, 1), due_date=date(2026, 7, 5), status='unpaid',
    )
    entries = build_ledger(org, date(2026, 7, 1), date(2026, 7, 31))
    dates = [e.date for e in entries]
    assert dates == sorted(dates)


@pytest.mark.django_db
def test_build_ledger_rejects_end_before_start(org):
    with pytest.raises(ValueError):
        build_ledger(org, date(2026, 7, 31), date(2026, 7, 1))


@pytest.mark.django_db
def test_build_ledger_is_org_scoped(org):
    from apps.organisations.models import Organisation
    other_org = Organisation.objects.create(name='Other Org', base_currency='USD')
    other_customer = Counterparty.objects.create(
        org=other_org, name='Other Org Client', type=Counterparty.TYPE_CUSTOMER,
    )
    Invoice.objects.create(
        org=other_org, counterparty=other_customer, amount=Decimal('999.00'), currency='USD',
        issue_date=date(2026, 7, 1), due_date=date(2026, 7, 15), status='unpaid',
    )
    entries = build_ledger(org, date(2026, 7, 1), date(2026, 7, 31))
    assert entries == ()
