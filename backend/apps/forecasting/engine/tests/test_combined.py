"""Combined Layer 1 + Layer 3 daily balance — mandatory money-handling coverage:
this is where deterministic and statistical amounts get added into a cumulative
Decimal balance with quantile bands, so arithmetic correctness, non-crossing
bands, and runway detection are all risk-relevant, not just smoke-test territory.
"""
from datetime import date, timedelta
from decimal import Decimal

import pytest
from django.utils import timezone

from apps.counterparties.models import Counterparty, Invoice
from apps.forecasting.engine.combined import (
    build_combined_daily_balance,
    compute_runway,
    summarize_drivers,
)
from apps.forecasting.engine.ledger import build_ledger
from apps.forecasting.engine.statistical import build_layer3_forecast
from apps.transactions.models import Transaction

pytestmark = pytest.mark.unit


def _seed_learning_stage_history(org):
    """Same deterministic pattern used by generate_synthetic_org's solo_trader
    preset — 4 uncategorised transactions, calibrated to land in 'learning' stage.
    """
    span, count, gap = 34, 4, 32
    offsets = [round(i * (span - 1) / (count - 1)) for i in range(count)]
    for i, offset in enumerate(offsets):
        days_ago = gap + (span - 1 - offset)
        amount = Decimal('200.00') if i % 2 == 0 else Decimal('-40.00')
        Transaction.objects.create(
            org=org, source=Transaction.SOURCE_MANUAL,
            timestamp=timezone.now() - timedelta(days=days_ago),
            amount=amount, currency=org.base_currency,
            base_amount=amount, base_currency=org.base_currency,
        )


@pytest.mark.django_db
def test_combined_balance_matches_independently_computed_layers(org):
    _seed_learning_stage_history(org)
    customer = Counterparty.objects.create(org=org, name='Client Co', type=Counterparty.TYPE_CUSTOMER)
    due_date = timezone.now().date() + timedelta(days=3)
    Invoice.objects.create(
        org=org, counterparty=customer, amount=Decimal('500.00'), currency=org.base_currency,
        issue_date=due_date - timedelta(days=10), due_date=due_date, status='unpaid',
    )

    starting_balance = Decimal('1000.00')
    points = build_combined_daily_balance(org, horizon_days=7, starting_balance=starting_balance)
    assert len(points) == 7

    stat_points = {p.date: p for p in build_layer3_forecast(org, horizon_days=7)}
    ledger_entries = build_ledger(org, points[0].date, points[-1].date)
    known_by_date: dict = {}
    for entry in ledger_entries:
        known_by_date[entry.date] = known_by_date.get(entry.date, Decimal('0')) + entry.amount

    running = starting_balance
    for point in points:
        expected_known = known_by_date.get(point.date, Decimal('0'))
        expected_stat = stat_points[point.date].p50 if point.date in stat_points else Decimal('0')
        assert point.known_net == expected_known
        assert point.statistical_p50 == expected_stat
        running += expected_known + expected_stat
        assert point.balance_p50 == running

    # The invoice's due date must show the known 500 exactly, with no uncertainty
    # attached to it (uncertainty is Layer 3's alone).
    invoice_day = next(p for p in points if p.date == due_date)
    assert invoice_day.known_net == Decimal('500.00')
    assert invoice_day.drivers.get('ar_invoice') == Decimal('500.00')


@pytest.mark.django_db
def test_combined_balance_bands_never_cross(org):
    _seed_learning_stage_history(org)
    points = build_combined_daily_balance(org, horizon_days=7, starting_balance=Decimal('500.00'))
    for point in points:
        assert point.balance_p10 <= point.balance_p50 <= point.balance_p90


@pytest.mark.django_db
def test_combined_balance_all_decimal(org):
    _seed_learning_stage_history(org)
    points = build_combined_daily_balance(org, horizon_days=5, starting_balance=Decimal('100.00'))
    for point in points:
        for field_name in ('known_net', 'statistical_p10', 'statistical_p50',
                           'statistical_p90', 'balance_p10', 'balance_p50', 'balance_p90'):
            assert isinstance(getattr(point, field_name), Decimal)


@pytest.mark.django_db
def test_combined_balance_falls_back_to_layer1_only_with_no_history(org):
    # A brand-new org: no transactions at all -> 'new' stage -> no statistical
    # forecast. The combined series must still reflect Layer 1's known items,
    # anchored on today, with the statistical component held at zero.
    customer = Counterparty.objects.create(org=org, name='Client Co', type=Counterparty.TYPE_CUSTOMER)
    due_date = timezone.now().date() + timedelta(days=2)
    Invoice.objects.create(
        org=org, counterparty=customer, amount=Decimal('300.00'), currency=org.base_currency,
        issue_date=due_date - timedelta(days=5), due_date=due_date, status='unpaid',
    )

    points = build_combined_daily_balance(org, horizon_days=5, starting_balance=Decimal('1000.00'))
    assert len(points) == 5
    assert points[0].date == timezone.now().date() + timedelta(days=1)
    assert all(p.statistical_p50 == Decimal('0') for p in points)
    invoice_day = next(p for p in points if p.date == due_date)
    assert invoice_day.known_net == Decimal('300.00')
    assert invoice_day.balance_p50 == Decimal('1300.00')


@pytest.mark.django_db
def test_runway_detects_worst_case_at_or_before_most_likely(org):
    _seed_learning_stage_history(org)
    supplier = Counterparty.objects.create(org=org, name='Big Bill Co', type=Counterparty.TYPE_SUPPLIER)
    from apps.forecasting.engine.models import Bill
    Bill.objects.create(
        org=org, counterparty=supplier, amount=Decimal('900.00'), currency=org.base_currency,
        issue_date=timezone.now().date(), due_date=timezone.now().date() + timedelta(days=2),
        status='unpaid',
    )
    points = build_combined_daily_balance(org, horizon_days=10, starting_balance=Decimal('1000.00'))
    runway = compute_runway(points, safety_buffer=Decimal('200.00'))
    # P10 (pessimistic) must cross the buffer no later than P50 (most likely) — the
    # worst-case path can never be rosier than the most-likely one.
    if runway.most_likely_cashout_date is not None and runway.worst_case_cashout_date is not None:
        assert runway.worst_case_cashout_date <= runway.most_likely_cashout_date


@pytest.mark.django_db
def test_runway_returns_none_when_balance_never_drops_below_buffer(org):
    _seed_learning_stage_history(org)
    points = build_combined_daily_balance(org, horizon_days=7, starting_balance=Decimal('1000000.00'))
    runway = compute_runway(points, safety_buffer=Decimal('0'))
    assert runway.most_likely_cashout_date is None
    assert runway.worst_case_cashout_date is None


@pytest.mark.django_db
def test_cumulative_band_grows_by_sqrt_n_not_linearly(org):
    # Regression for a real bug found against real imported bank data: summing
    # each day's P10/P90 offset linearly into the cumulative balance produced
    # a 14-day band roughly 14x a single day's spread (effectively assuming
    # the same worst-case deviation recurs every day simultaneously). With N
    # days of roughly equal daily uncertainty, the correct cumulative spread
    # from independent variance additivity is sqrt(N)x a single day's spread,
    # not Nx.
    _seed_learning_stage_history(org)
    points = build_combined_daily_balance(org, horizon_days=14, starting_balance=Decimal('10000.00'))
    assert len(points) == 14

    day1_p10_spread = points[0].balance_p50 - points[0].balance_p10
    day14_p10_spread = points[13].balance_p50 - points[13].balance_p10
    if day1_p10_spread == 0:
        pytest.skip('degenerate band (no backtest residuals yet) — nothing to compare growth against')

    # Naive linear summation would give ~14x day-1's spread by day 14; sqrt(14)
    # is ~3.74x. Assert it's well below the old linear-sum behaviour, with
    # headroom for the fact that per-day spreads aren't perfectly identical.
    assert day14_p10_spread < day1_p10_spread * Decimal('8')


@pytest.mark.django_db
def test_known_layer1_amounts_never_widen_the_band(org):
    # A known, deterministic invoice/bill must not add any uncertainty — only
    # Layer 3's statistical component should ever widen p10/p90. Isolate this
    # by comparing the SAME day's band width with vs. without the invoice
    # present (not two different days, which would confound the comparison
    # with each day's own distinct statistical offset).
    _seed_learning_stage_history(org)
    due_date = timezone.now().date() + timedelta(days=3)

    points_without = build_combined_daily_balance(org, horizon_days=7, starting_balance=Decimal('1000.00'))
    day_without = next(p for p in points_without if p.date == due_date)
    width_without = day_without.balance_p90 - day_without.balance_p10

    customer = Counterparty.objects.create(org=org, name='Big Client', type=Counterparty.TYPE_CUSTOMER)
    Invoice.objects.create(
        org=org, counterparty=customer, amount=Decimal('9999999.00'), currency=org.base_currency,
        issue_date=due_date - timedelta(days=10), due_date=due_date, status='unpaid',
    )
    points_with = build_combined_daily_balance(org, horizon_days=7, starting_balance=Decimal('1000.00'))
    day_with = next(p for p in points_with if p.date == due_date)
    width_with = day_with.balance_p90 - day_with.balance_p10

    assert width_with == width_without
    # Only the P50 midpoint shifts, by exactly the known invoice amount.
    assert day_with.balance_p50 - day_without.balance_p50 == Decimal('9999999.00')


@pytest.mark.django_db
def test_summarize_drivers_sums_known_and_statistical_contributions(org):
    _seed_learning_stage_history(org)
    customer = Counterparty.objects.create(org=org, name='Client Co', type=Counterparty.TYPE_CUSTOMER)
    due_date = timezone.now().date() + timedelta(days=3)
    Invoice.objects.create(
        org=org, counterparty=customer, amount=Decimal('500.00'), currency=org.base_currency,
        issue_date=due_date - timedelta(days=10), due_date=due_date, status='unpaid',
    )
    points = build_combined_daily_balance(org, horizon_days=7, starting_balance=Decimal('1000.00'))
    totals = summarize_drivers(points)
    assert totals.get('ar_invoice') == Decimal('500.00')
    assert 'statistical_baseline' in totals
