"""Layer 3 statistical forecasting — risk-based coverage per the money-handling bar:
method selection by maturity stage, gap-filling correctness, and the two forecasting
algorithms themselves are the expensive-to-get-wrong logic here.
"""
from datetime import timedelta
from decimal import Decimal

import pytest
from django.utils import timezone

from apps.forecasting.engine.statistical import (
    METHOD_ETS,
    METHOD_NAIVE,
    _build_daily_series,
    _method_for_stage,
    build_layer3_forecast,
)
from apps.transactions.models import Transaction

pytestmark = pytest.mark.unit


def _make_txn(org, *, days_ago, amount):
    return Transaction.objects.create(
        org=org,
        source=Transaction.SOURCE_MANUAL,
        timestamp=timezone.now() - timedelta(days=days_ago),
        amount=Decimal(str(amount)),
        currency=org.base_currency,
        base_amount=Decimal(str(amount)),
        base_currency=org.base_currency,
    )


def test_method_for_stage_mapping():
    assert _method_for_stage('new') == 'insufficient_data'
    assert _method_for_stage('learning') == METHOD_NAIVE
    assert _method_for_stage('developing') == METHOD_ETS
    assert _method_for_stage('established') == METHOD_ETS
    assert _method_for_stage('expert') == METHOD_ETS


@pytest.mark.django_db
def test_build_layer3_forecast_returns_empty_with_no_data(org):
    assert build_layer3_forecast(org) == ()


@pytest.mark.django_db
def test_daily_series_gap_fills_missing_days(org):
    _make_txn(org, days_ago=5, amount=100)
    _make_txn(org, days_ago=0, amount=50)
    series = _build_daily_series(org)
    assert len(series) == 6  # days_ago=5 .. days_ago=0 inclusive
    dates = [d for d, _ in series]
    assert dates == sorted(dates)
    values_by_date = dict(series)
    # The 4 in-between days have no transactions and must be filled with 0.0, not skipped.
    non_edge_values = list(values_by_date.values())[1:-1]
    assert non_edge_values == [0.0, 0.0, 0.0, 0.0]


@pytest.mark.django_db
def test_daily_series_sums_multiple_transactions_same_day(org):
    _make_txn(org, days_ago=1, amount=100)
    _make_txn(org, days_ago=1, amount=-30)
    _make_txn(org, days_ago=0, amount=10)
    series = _build_daily_series(org)
    values = [v for _, v in series]
    assert values[0] == pytest.approx(70.0)


@pytest.mark.django_db
def test_short_history_org_gets_naive_fallback_regardless_of_stage(org):
    # 10 days of full daily manual-source data actually lands in 'developing' per
    # calculate_maturity's real scoring (100% coverage density + the reconciliation
    # exemption already floor the score there) — but 10 days is still below the
    # 2-seasonal-cycle (14 day) floor _ets_seasonal_forecast needs, so the ETS path
    # must fall back to naive rather than returning nothing. That fallback, not a
    # 'learning' stage classification, is what this test actually verifies.
    for i in range(10):
        _make_txn(org, days_ago=i, amount=100 + (i % 3) * 10)

    points = build_layer3_forecast(org)
    assert len(points) > 0
    assert all(p.method == METHOD_NAIVE for p in points)
    assert all(isinstance(p.p50, Decimal) for p in points)
    assert all(p.p10 <= p.p50 <= p.p90 for p in points)
    # Forecast dates must be strictly after the last historical day, consecutive.
    dates = [p.date for p in points]
    assert dates == sorted(dates)
    assert len(dates) == len(set(dates))


@pytest.mark.django_db
def test_naive_forecast_explicit_horizon_overrides_stage_horizon(org):
    for i in range(10):
        _make_txn(org, days_ago=i, amount=100)
    points = build_layer3_forecast(org, horizon_days=3)
    assert len(points) == 3


@pytest.mark.django_db
def test_naive_forecast_insufficient_history_returns_empty(org):
    # 3 days of data is below _MIN_HISTORY_DAYS_FOR_NAIVE even if stage happened to
    # allow a method — the per-method history floor is a separate, harder guard.
    for i in range(3):
        _make_txn(org, days_ago=i, amount=100)
    points = build_layer3_forecast(org, horizon_days=7)
    assert points == ()


@pytest.mark.django_db
def test_developing_stage_uses_ets_with_enough_history(org):
    # 90 days of bank-feed-reliability data with a clear weekly pattern pushes the
    # org well past 'learning' into ETS territory, and gives statsmodels enough
    # seasonal cycles (>=2x7) to fit without falling back to naive.
    for i in range(90):
        weekday_boost = 40 if (i % 7) in (5, 6) else 0
        Transaction.objects.create(
            org=org, source=Transaction.SOURCE_BANK_FEED,
            timestamp=timezone.now() - timedelta(days=i),
            amount=Decimal(str(200 + weekday_boost)),
            currency=org.base_currency,
            base_amount=Decimal(str(200 + weekday_boost)),
            base_currency=org.base_currency,
            category_overridden=True,
        )
    points = build_layer3_forecast(org, horizon_days=14)
    assert len(points) == 14
    assert all(p.method in (METHOD_ETS, METHOD_NAIVE) for p in points)
    assert all(isinstance(p.p50, Decimal) for p in points)
    assert all(p.p10 <= p.p50 <= p.p90 for p in points)
    dates = [p.date for p in points]
    assert dates == sorted(dates)


@pytest.mark.django_db
def test_ets_forecast_falls_back_to_naive_when_history_is_years_stale(org):
    # Regression for a real bug found against real imported bank data: an org
    # whose last transaction was ~5 years ago (real historic bank export, not
    # a synthetic fixture) has ETS asked to extrapolate its trend thousands of
    # days forward to reach 'today' — additive-trend prediction-interval
    # variance compounds per step and blew up to 9-figure bands on data whose
    # actual values were in the hundreds of thousands. Beyond
    # _MAX_STALE_GAP_DAYS_FOR_ETS, the ETS path must fall back to naive rather
    # than return a numerically absurd result.
    from apps.forecasting.engine.statistical import _build_daily_series, _ets_seasonal_forecast

    for i in range(90):
        weekday_boost = 40 if (i % 7) in (5, 6) else 0
        days_ago = i + 400  # last transaction ~310 days before "today" at the closest
        Transaction.objects.create(
            org=org, source=Transaction.SOURCE_BANK_FEED,
            timestamp=timezone.now() - timedelta(days=days_ago),
            amount=Decimal(str(200 + weekday_boost)),
            currency=org.base_currency,
            base_amount=Decimal(str(200 + weekday_boost)),
            base_currency=org.base_currency,
        )
    series = _build_daily_series(org)
    points = _ets_seasonal_forecast(series, horizon_days=14)
    assert len(points) == 14
    assert all(p.method == METHOD_NAIVE for p in points)
    # Sanity: bands must stay in a plausible range relative to the input data's
    # own scale (a few hundred units), not blow up to millions.
    assert all(abs(p.p10) < Decimal('100000') for p in points)
    assert all(abs(p.p90) < Decimal('100000') for p in points)


@pytest.mark.django_db
def test_ets_forecast_falls_back_to_naive_below_two_seasonal_cycles(org):
    # 10 days is below 2*7=14, so even if maturity somehow selected ETS, the
    # forecast function itself must fall back rather than crash statsmodels.
    from apps.forecasting.engine.statistical import _build_daily_series, _ets_seasonal_forecast
    for i in range(10):
        _make_txn(org, days_ago=i, amount=100)
    series = _build_daily_series(org)
    points = _ets_seasonal_forecast(series, horizon_days=5)
    assert len(points) == 5
    assert all(p.method == METHOD_NAIVE for p in points)


@pytest.mark.django_db
def test_naive_band_is_degenerate_with_too_few_backtest_residuals(org):
    # Exactly _MIN_HISTORY_DAYS_FOR_NAIVE=7 days of history gives zero backtest
    # residuals (the backtest loop starts at index 7, which doesn't exist yet) —
    # the band must collapse to the point forecast, not invent a spread.
    for i in range(7):
        _make_txn(org, days_ago=i, amount=100)
    points = build_layer3_forecast(org, horizon_days=3)
    assert len(points) == 3
    assert all(p.p10 == p.p50 == p.p90 for p in points)


@pytest.mark.django_db
def test_naive_band_is_nondegenerate_with_enough_backtest_history(org):
    # 40 days with real day-to-day variability gives enough backtest residuals
    # for a genuine, non-collapsed P10/P90 spread.
    for i in range(40):
        _make_txn(org, days_ago=i, amount=100 + (i % 5) * 30 - (i % 3) * 15)
    points = build_layer3_forecast(org, horizon_days=5)
    assert len(points) == 5
    assert all(p.p10 < p.p50 < p.p90 for p in points)


@pytest.mark.django_db
def test_ets_band_is_nondegenerate(org):
    for i in range(90):
        weekday_boost = 60 if (i % 7) in (5, 6) else 0
        Transaction.objects.create(
            org=org, source=Transaction.SOURCE_BANK_FEED,
            timestamp=timezone.now() - timedelta(days=i),
            amount=Decimal(str(200 + weekday_boost + (i % 4) * 10)),
            currency=org.base_currency,
            base_amount=Decimal(str(200 + weekday_boost + (i % 4) * 10)),
            base_currency=org.base_currency,
        )
    points = build_layer3_forecast(org, horizon_days=10)
    assert len(points) == 10
    assert all(p.method == METHOD_ETS for p in points)
    assert all(p.p10 < p.p50 < p.p90 for p in points)


@pytest.mark.django_db
def test_known_invoice_matched_transaction_excluded_from_training_series(org):
    from apps.counterparties.models import Counterparty, Invoice

    customer = Counterparty.objects.create(org=org, name='Big Client', type=Counterparty.TYPE_CUSTOMER)
    _make_txn(org, days_ago=15, amount=80)  # unmatched activity, before the known one
    known_txn = _make_txn(org, days_ago=10, amount=50000)  # a huge known AR payment
    Invoice.objects.create(
        org=org, counterparty=customer, amount=Decimal('50000.00'), currency='GBP',
        issue_date=known_txn.timestamp.date() - timedelta(days=5),
        due_date=known_txn.timestamp.date(), paid_date=known_txn.timestamp.date(),
        status='paid', matched_transaction=known_txn,
    )
    _make_txn(org, days_ago=5, amount=100)  # ordinary unmatched activity, after

    series = _build_daily_series(org)
    values_by_date = dict(series)
    known_day = known_txn.timestamp.date()
    # The known, Layer-1-matched 50000 must not appear in Layer 3's training series —
    # that day should be gap-filled to 0.0, not carry the matched invoice's amount.
    assert values_by_date[known_day] == 0.0


@pytest.mark.django_db
def test_naive_forecast_anchors_on_today_not_stale_last_transaction(org):
    # History ends 20 days ago (a genuinely common "behind on bookkeeping" pattern,
    # not an abandoned org) — the forecast must still start from today forward,
    # never resume from 20 days in the past.
    for i in range(20, 30):
        _make_txn(org, days_ago=i, amount=100)
    points = build_layer3_forecast(org, horizon_days=5)
    assert len(points) == 5
    today = timezone.now().date()
    assert points[0].date == today + timedelta(days=1)
    assert points[-1].date == today + timedelta(days=5)
    assert all(p.date > today for p in points)


@pytest.mark.django_db
def test_ets_forecast_anchors_on_today_not_stale_last_transaction(org):
    for i in range(20, 20 + 90):
        weekday_boost = 40 if (i % 7) in (5, 6) else 0
        Transaction.objects.create(
            org=org, source=Transaction.SOURCE_BANK_FEED,
            timestamp=timezone.now() - timedelta(days=i),
            amount=Decimal(str(200 + weekday_boost)),
            currency=org.base_currency,
            base_amount=Decimal(str(200 + weekday_boost)),
            base_currency=org.base_currency,
        )
    points = build_layer3_forecast(org, horizon_days=5)
    assert len(points) == 5
    today = timezone.now().date()
    assert points[0].date == today + timedelta(days=1)
    assert points[-1].date == today + timedelta(days=5)
    assert all(p.method == METHOD_ETS for p in points)


@pytest.mark.django_db
def test_known_bill_matched_transaction_excluded_from_training_series(org):
    from apps.counterparties.models import Counterparty
    from apps.forecasting.engine.models import Bill

    supplier = Counterparty.objects.create(org=org, name='Big Supplier', type=Counterparty.TYPE_SUPPLIER)
    _make_txn(org, days_ago=15, amount=-80)  # unmatched activity, before the known one
    known_txn = _make_txn(org, days_ago=10, amount=-30000)  # a huge known AP payment
    Bill.objects.create(
        org=org, counterparty=supplier, amount=Decimal('30000.00'), currency='GBP',
        issue_date=known_txn.timestamp.date() - timedelta(days=5),
        due_date=known_txn.timestamp.date(), paid_date=known_txn.timestamp.date(),
        status='paid', matched_transaction=known_txn,
    )
    _make_txn(org, days_ago=5, amount=-100)  # ordinary unmatched activity, after

    series = _build_daily_series(org)
    values_by_date = dict(series)
    assert values_by_date[known_txn.timestamp.date()] == 0.0
