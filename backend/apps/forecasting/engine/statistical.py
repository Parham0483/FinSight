"""Layer 3 — maturity-appropriate statistical forecasting (blueprint §3 Layer 3, §8 Phase 2).

Two methods, chosen by `DataMaturity` stage — not a user choice:

  - **learning** stage: weekly-pattern naive + trailing average. A trailing mean
    baseline plus an additive day-of-week seasonal offset learned from history.
    Deliberately simple — "learning" stage means there isn't enough history for
    anything fancier, and pretending otherwise would be dishonest per the
    maturity system's own design principle (see `maturity.py`). Uncertainty
    bands come from backtested in-sample residual spread (P10/P90 of actual
    minus naive-predicted, walked forward day by day) — not invented.
  - **developing** stage and above: ETS (error-trend-seasonal exponential
    smoothing, `statsmodels.tsa.exponential_smoothing.ets.ETSModel`) with
    weekly seasonality. Uncertainty bands come from ETS's own native
    prediction intervals (`get_prediction().summary_frame(alpha=0.20)`, which
    is exactly the P10-P90 range) — not invented either.

Gradient boosting / Prophet-class models are explicitly NOT built here — per
PHASE_DIRECTIVE.md, that's gated on Phase 3 proving an accuracy need, not a
Phase 2 requirement.

Both methods forecast daily net cash flow (inflow - outflow, base currency)
built from `Transaction` history by `_build_daily_series`, which:
  1. gap-fills missing days with 0.0 so weekly seasonality isn't distorted by
     silent gaps, and
  2. excludes transactions already matched to a `counterparties.Invoice` or
     `Bill` — those are Layer 1's deterministic, already-known territory, and
     Layer 3 must forecast only what *isn't* already known or it would double
     count when the two layers are combined (see `combined.py`).

The forecast's day-1 is always anchored at `max(last historical day, today) + 1`
— never in the past. An org whose last transaction was weeks ago (a genuinely
common "behind on bookkeeping" pattern, not just an abandoned business) still
gets a forecast that starts from today forward, using its real historical
pattern to inform the trailing average / seasonal offsets / ETS fit; the model
is never asked to "predict" days that have already elapsed. Confirmed this
matters in practice, not just in theory: without this anchor, a stale-but-live
org's forecast window silently landed entirely in the past relative to "today",
which is useless input for `combined.py`'s daily balance projection.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal

from django.utils import timezone

from apps.forecasting.maturity import calculate_maturity
from apps.organisations.models import Organisation

_TRAILING_WINDOW_DAYS = 28
_MIN_HISTORY_DAYS_FOR_NAIVE = 7
_MIN_BACKTEST_RESIDUALS_FOR_BAND = 3
_WEEKLY_SEASONAL_PERIOD = 7
_INTERVAL_ALPHA = 0.20  # alpha=0.20 -> 80% CI -> exactly the P10-P90 range
# ETS's additive-trend prediction-interval variance compounds per forecast step —
# asking it to extrapolate hundreds/thousands of steps forward (to bridge from a
# years-stale org's last transaction to "today") produces numerically absurd
# bands (confirmed empirically: a ~1,980-day gap blew up P10/P90 to nine figures
# on data whose actual values were in the hundreds of thousands). Beyond this
# many stale days, ETS's fitted trend is not a trustworthy predictor of "today"
# anyway — fall back to the naive method, which doesn't compound error the same
# way, rather than silently returning a technically-computed but meaningless band.
_MAX_STALE_GAP_DAYS_FOR_ETS = 180

METHOD_NAIVE = 'naive_weekly_trailing_average'
METHOD_ETS = 'ets_seasonal'
METHOD_NONE = 'insufficient_data'


@dataclass(frozen=True)
class StatisticalForecastPoint:
    date: date
    p10: Decimal
    p50: Decimal
    p90: Decimal
    method: str


def _method_for_stage(stage: str) -> str:
    if stage == 'learning':
        return METHOD_NAIVE
    if stage in ('developing', 'established', 'expert'):
        return METHOD_ETS
    return METHOD_NONE


def _known_transaction_ids(org: Organisation) -> set:
    """IDs of transactions already matched to a Layer 1 Invoice/Bill — Layer 3 must
    not train on these, or the combined projection double-counts them (see module docstring).
    """
    from apps.counterparties.models import Invoice

    from .models import Bill

    invoice_ids = set(
        Invoice.objects.filter(org=org, matched_transaction__isnull=False)
        .values_list('matched_transaction_id', flat=True)
    )
    bill_ids = set(
        Bill.objects.filter(org=org, matched_transaction__isnull=False)
        .values_list('matched_transaction_id', flat=True)
    )
    return invoice_ids | bill_ids


def _build_daily_series(org: Organisation) -> list[tuple[date, float]]:
    """Daily net cash flow (base currency) excluding known Layer-1-matched
    transactions, gap-filled with 0.0, oldest-first.
    """
    from django.db.models import Sum
    from django.db.models.functions import Coalesce, TruncDate

    from apps.transactions.models import Transaction

    known_ids = _known_transaction_ids(org)
    rows = (
        Transaction.objects.filter(org=org)
        .exclude(id__in=known_ids)
        .annotate(day=TruncDate('timestamp'), net_amount=Coalesce('base_amount', 'amount'))
        .values('day')
        .annotate(net=Sum('net_amount'))
        .order_by('day')
    )
    by_day = {row['day']: float(row['net'] or 0) for row in rows}
    if not by_day:
        return []

    start, end = min(by_day), max(by_day)
    series: list[tuple[date, float]] = []
    cursor = start
    while cursor <= end:
        series.append((cursor, by_day.get(cursor, 0.0)))
        cursor += timedelta(days=1)
    return series


def _forecast_anchor_date(series: list[tuple[date, float]]) -> date:
    """The last day BEFORE forecasting starts — never earlier than today, even if
    the org's real history is stale. See module docstring for why this matters.
    """
    last_historical_date = series[-1][0]
    today = timezone.now().date()
    return max(last_historical_date, today)


def _compute_naive_baseline(series: list[tuple[date, float]]) -> tuple[float, dict[int, float]]:
    """Trailing average + additive day-of-week seasonal offsets, from `series` alone."""
    values = [v for _, v in series]
    trailing = values[-_TRAILING_WINDOW_DAYS:] if len(values) > _TRAILING_WINDOW_DAYS else values
    trailing_average = sum(trailing) / len(trailing)

    overall_mean = sum(values) / len(values)
    weekday_totals = {i: 0.0 for i in range(7)}
    weekday_counts = {i: 0 for i in range(7)}
    for day, value in series:
        wd = day.weekday()
        weekday_totals[wd] += value - overall_mean
        weekday_counts[wd] += 1
    weekday_offsets = {
        wd: (weekday_totals[wd] / weekday_counts[wd] if weekday_counts[wd] else 0.0)
        for wd in range(7)
    }
    return trailing_average, weekday_offsets


def _naive_backtest_residuals(series: list[tuple[date, float]]) -> list[float]:
    """Walk-forward residuals (actual - naive-predicted) using only data available
    at each historical point — a real backtest, not a lookahead-biased fit.
    """
    residuals = []
    for i in range(_MIN_HISTORY_DAYS_FOR_NAIVE, len(series)):
        train = series[:i]
        actual_date, actual_value = series[i]
        trailing_average, weekday_offsets = _compute_naive_baseline(train)
        predicted = trailing_average + weekday_offsets.get(actual_date.weekday(), 0.0)
        residuals.append(actual_value - predicted)
    return residuals


def _naive_weekly_trailing_forecast(
    series: list[tuple[date, float]], horizon_days: int,
) -> list[StatisticalForecastPoint]:
    """Trailing average baseline + additive day-of-week seasonal offset, with
    P10/P90 bands from backtested in-sample residual spread.
    """
    import numpy as np

    trailing_average, weekday_offsets = _compute_naive_baseline(series)
    residuals = _naive_backtest_residuals(series)
    if len(residuals) >= _MIN_BACKTEST_RESIDUALS_FOR_BAND:
        low_offset, high_offset = np.percentile(residuals, [10, 90])
    else:
        # Too little history for a meaningful residual distribution — no band yet,
        # not an invented one.
        low_offset = high_offset = 0.0

    anchor_date = _forecast_anchor_date(series)
    points = []
    for i in range(1, horizon_days + 1):
        forecast_date = anchor_date + timedelta(days=i)
        predicted = trailing_average + weekday_offsets[forecast_date.weekday()]
        points.append(StatisticalForecastPoint(
            date=forecast_date,
            p10=Decimal(str(round(predicted + low_offset, 2))),
            p50=Decimal(str(round(predicted, 2))),
            p90=Decimal(str(round(predicted + high_offset, 2))),
            method=METHOD_NAIVE,
        ))
    return points


def _ets_seasonal_forecast(
    series: list[tuple[date, float]], horizon_days: int,
) -> list[StatisticalForecastPoint]:
    """ETS (error-trend-seasonal) exponential smoothing with weekly seasonality,
    using statsmodels' own prediction intervals for the P10/P90 band.
    """
    import pandas as pd
    from statsmodels.tsa.exponential_smoothing.ets import ETSModel

    values = [v for _, v in series]
    last_date = series[-1][0]
    anchor_date = _forecast_anchor_date(series)
    # Days between the last real data point and the forecast anchor (0 for a live,
    # up-to-date org) — the model must step through these too, but they're discarded
    # below since they'd otherwise land in the past relative to `anchor_date`.
    stale_gap_days = (anchor_date - last_date).days

    # statsmodels needs >= 2 full seasonal cycles to fit a seasonal model;
    # fall back to the naive method rather than raising on borderline history.
    if len(values) < _WEEKLY_SEASONAL_PERIOD * 2:
        return _naive_weekly_trailing_forecast(series, horizon_days)

    # See _MAX_STALE_GAP_DAYS_FOR_ETS docstring above — don't ask ETS to
    # extrapolate its trend across a multi-month-or-longer gap.
    if stale_gap_days > _MAX_STALE_GAP_DAYS_FOR_ETS:
        return _naive_weekly_trailing_forecast(series, horizon_days)

    endog = pd.Series(values)
    model = ETSModel(
        endog, error='add', trend='add', seasonal='add', seasonal_periods=_WEEKLY_SEASONAL_PERIOD,
    )
    fit = model.fit()
    n = len(values)
    total_steps = stale_gap_days + horizon_days
    prediction = fit.get_prediction(start=n, end=n + total_steps - 1)
    summary = prediction.summary_frame(alpha=_INTERVAL_ALPHA).iloc[stale_gap_days:]

    points = []
    for i, row in enumerate(summary.itertuples(), start=1):
        forecast_date = anchor_date + timedelta(days=i)
        points.append(StatisticalForecastPoint(
            date=forecast_date,
            p10=Decimal(str(round(float(row.pi_lower), 2))),
            p50=Decimal(str(round(float(row.mean), 2))),
            p90=Decimal(str(round(float(row.pi_upper), 2))),
            method=METHOD_ETS,
        ))
    return points


def build_layer3_forecast(
    org: Organisation, horizon_days: int | None = None,
) -> tuple[StatisticalForecastPoint, ...]:
    """Project daily net cash flow `horizon_days` ahead, method chosen by maturity stage."""
    profile = calculate_maturity(str(org.id))
    method = _method_for_stage(profile.stage)
    horizon = horizon_days if horizon_days is not None else profile.forecast_horizon_days

    if method == METHOD_NONE or horizon <= 0:
        return ()

    series = _build_daily_series(org)
    if len(series) < _MIN_HISTORY_DAYS_FOR_NAIVE:
        return ()

    if method == METHOD_NAIVE:
        return tuple(_naive_weekly_trailing_forecast(series, horizon))

    # ETS falls back to the naive method internally when history is too short
    # for a seasonal fit — that fallback must actually run, not be pre-empted here.
    return tuple(_ets_seasonal_forecast(series, horizon))
