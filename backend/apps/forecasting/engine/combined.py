"""Combined daily balance projection — Layer 1 (deterministic) + Layer 3 (statistical),
runway, and driver attribution (blueprint §3, §8 Phase 2).

Layer 1's ledger entries are exact and carry no uncertainty; Layer 3's statistical
forecast (see `statistical.py`) already excludes anything Layer 1 tracks, so the two
combine additively without double-counting. The P10/P50/P90 spread on each combined
day comes entirely from Layer 3's own uncertainty — Layer 1's contribution is
identical across all three quantiles, because a known invoice due date isn't a
probabilistic estimate.

The forecast date range is anchored off whatever dates Layer 3 actually produces
(which start the day after the org's last historical transaction, not necessarily
"today" for a stale org) rather than an independently-chosen range, so the two
layers are always combined over exactly the same days. If Layer 3 has no forecast
at all (an org still in the 'new' maturity stage), the combined series falls back
to Layer 1 alone, anchored on today, with the statistical component held at zero —
documented as "no statistical forecast yet", not silently pretended away.

Cumulative band math: the P50 (most-likely) running balance is a plain running
sum — expectations of independent daily flows add linearly regardless of
correlation, so that part is exact. The P10/P90 band width is NOT summed
linearly day over day; each day's own (p50-p10)/(p90-p50) offset is treated as
a variance proxy and combined via variance additivity (cumulative_variance =
sum of each day's offset squared; cumulative band = sqrt(cumulative_variance)),
so N days of independent daily uncertainty grow the cumulative band by
sqrt(N), not N. Confirmed empirically this matters, not just in theory: naive
linear summation was checked against real imported bank data and produced a
14-day P10/P90 spread of roughly ±14 million against a starting balance of
50,000 and single-day spreads of only a few hundred thousand — the same
"worst day" was effectively being assumed to recur on every single day of the
horizon simultaneously, which overstates cumulative uncertainty by an order
of magnitude and would have been exactly the kind of invented-not-derived
band the money-handling rules warn against. This is a closed-form
approximation (assumes daily residuals are roughly independent), not a Monte
Carlo simulation — actual path-sampling uncertainty propagation is Phase 4's
Monte Carlo assembly, explicitly out of scope here.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal

from django.utils import timezone

from apps.organisations.models import Organisation

from .ledger import build_ledger
from .statistical import build_layer3_forecast

_TWO_DP = Decimal('0.01')


def _money(value: Decimal) -> Decimal:
    """Round to money precision. Decimal.sqrt() (used for band-width variance
    additivity below) returns dozens of digits of precision that aren't
    meaningful for a currency amount — quantize at the point of computation,
    consistent with every other money value in this codebase.
    """
    return value.quantize(_TWO_DP, rounding=ROUND_HALF_UP)


@dataclass(frozen=True)
class DailyBalancePoint:
    date: date
    known_net: Decimal            # Layer 1's exact contribution that day (no uncertainty)
    statistical_p10: Decimal
    statistical_p50: Decimal
    statistical_p90: Decimal
    balance_p10: Decimal          # cumulative projected balance, pessimistic
    balance_p50: Decimal          # cumulative projected balance, most likely
    balance_p90: Decimal          # cumulative projected balance, optimistic
    drivers: dict = field(default_factory=dict)  # source_type -> Decimal contribution
    statistical_method: str | None = None  # Layer 3 method used that day, or None if no forecast


@dataclass(frozen=True)
class RunwayResult:
    most_likely_cashout_date: date | None  # first date balance_p50 drops below the buffer
    worst_case_cashout_date: date | None   # first date balance_p10 drops below the buffer


def build_combined_daily_balance(
    org: Organisation, horizon_days: int, starting_balance: Decimal,
) -> tuple[DailyBalancePoint, ...]:
    """Project daily balance `horizon_days` ahead: Layer 1's known flows plus Layer 3's
    statistical forecast for whatever isn't already known, with P10/P50/P90 bands.
    """
    statistical_points = build_layer3_forecast(org, horizon_days=horizon_days)
    stat_by_date = {p.date: p for p in statistical_points}

    if statistical_points:
        forecast_dates = [p.date for p in statistical_points]
    else:
        today = timezone.now().date()
        forecast_dates = [today + timedelta(days=i) for i in range(1, horizon_days + 1)]

    start_date, end_date = forecast_dates[0], forecast_dates[-1]
    ledger_entries = build_ledger(org, start_date, end_date)

    known_by_date: dict[date, Decimal] = {d: Decimal('0') for d in forecast_dates}
    drivers_by_date: dict[date, dict[str, Decimal]] = {d: {} for d in forecast_dates}
    for entry in ledger_entries:
        known_by_date[entry.date] = known_by_date[entry.date] + entry.amount
        drivers_by_date[entry.date][entry.source_type] = (
            drivers_by_date[entry.date].get(entry.source_type, Decimal('0')) + entry.amount
        )

    points = []
    running_p50 = starting_balance
    cumulative_low_variance = Decimal('0')
    cumulative_high_variance = Decimal('0')
    for d in forecast_dates:
        known_net = known_by_date[d]
        stat_point = stat_by_date.get(d)
        s10, s50, s90 = (stat_point.p10, stat_point.p50, stat_point.p90) if stat_point else (
            Decimal('0'), Decimal('0'), Decimal('0'),
        )

        # P50 is a plain running sum — expectations of daily flows add linearly.
        running_p50 += known_net + s50
        # Band width uses variance additivity, not linear summation — see module
        # docstring for why (naive linear summation was checked against real
        # data and produced absurd multi-million-unit bands).
        low_offset = s50 - s10
        high_offset = s90 - s50
        cumulative_low_variance += low_offset * low_offset
        cumulative_high_variance += high_offset * high_offset
        balance_p10 = _money(running_p50 - cumulative_low_variance.sqrt())
        balance_p90 = _money(running_p50 + cumulative_high_variance.sqrt())

        drivers = dict(drivers_by_date[d])
        if stat_point is not None:
            drivers['statistical_baseline'] = s50

        points.append(DailyBalancePoint(
            date=d,
            known_net=known_net,
            statistical_p10=s10, statistical_p50=s50, statistical_p90=s90,
            balance_p10=balance_p10, balance_p50=running_p50, balance_p90=balance_p90,
            drivers=drivers,
            statistical_method=stat_point.method if stat_point else None,
        ))
    return tuple(points)


def compute_runway(
    points: tuple[DailyBalancePoint, ...], safety_buffer: Decimal = Decimal('0'),
) -> RunwayResult:
    """First date the most-likely (P50) and worst-case (P10) balance paths drop
    below `safety_buffer`. None if the balance never drops that low within the horizon.
    """
    most_likely = next((p.date for p in points if p.balance_p50 < safety_buffer), None)
    worst_case = next((p.date for p in points if p.balance_p10 < safety_buffer), None)
    return RunwayResult(most_likely_cashout_date=most_likely, worst_case_cashout_date=worst_case)


def summarize_drivers(points: tuple[DailyBalancePoint, ...]) -> dict[str, Decimal]:
    """Total contribution per driver (ar_invoice / ap_bill / recurring_obligation /
    statistical_baseline) summed across the whole horizon — the top-line breakdown of
    what's actually moving the combined balance.
    """
    totals: dict[str, Decimal] = {}
    for point in points:
        for source_type, amount in point.drivers.items():
            totals[source_type] = totals.get(source_type, Decimal('0')) + amount
    return totals
