"""
Forecast maturity system — determines what level of intelligence is available
for an organisation based on the *quality* of its accumulated data, not just
how much calendar time has passed.

Blueprint v2.2 §2.1: a pure day-count model is dishonest — 3 transactions
spanning 181 days would wrongly rate "expert"; a sparse, uncategorised ledger
would wrongly rate equal to a clean, reconciled one. The five-stage UX,
mascot moods, and capability gating are unchanged from v1 — only the input
becomes a composite score instead of a single day-count.

Composite DataMaturity score (0-100), weighted from six components:

  History span         30%  days between first/last transaction, capped at 365
  Coverage density      25%  days-with-data ÷ span (gaps reduce the score)
  Categorisation rate   15%  % of transactions with a category
  Source reliability    15%  bank-connected > documents > manual
  Reconciliation rate   10%  % of invoices/documents matched to a transaction
  Recency                5%  days since last data point (stale data decays)

Stages map from the composite score: new <5, learning 5-25, developing
25-50, established 50-75, expert 75+ — per the blueprint's explicit bucket
boundaries.

Explicit fast-forward rule (per spec): importing two years of bank history
on day one should jump an org straight to established/expert — that's the
history-span + source-reliability components doing exactly what they're
meant to, not an accident to guard against.
"""

from dataclasses import dataclass
from datetime import timedelta
from decimal import Decimal
from typing import TypedDict

from django.utils import timezone


class ComponentScores(TypedDict):
    history_span: float
    coverage_density: float
    categorisation_rate: float
    source_reliability: float
    reconciliation_rate: float
    recency: float


@dataclass(frozen=True)
class MaturityProfile:
    stage: str                        # new / learning / developing / established / expert
    score: float                      # composite 0-100 score driving the stage
    component_scores: ComponentScores  # per-component breakdown (blueprint §6 trust infra)
    days_of_data: int                 # raw history-span input, kept for API compatibility
    forecast_horizon_days: int         # max days the forecast will cover
    progress_to_next: float           # 0.0-1.0 toward the next stage, by score
    mascot_message: str
    mascot_mood: str
    capabilities: list[str]
    # Legacy field name from the day-count model. Now holds the composite
    # score points needed to reach the next stage (not a day count) — no
    # current frontend consumer reads this field's value, only
    # `next_milestone_label`, so repurposing it is safe. Kept as an int
    # field for API-shape compatibility.
    next_milestone_days: int
    next_milestone_label: str


# Stage definitions: only `min_score`/`max_score` are new. `horizon`,
# `message`, `mood`, and `capabilities` are unchanged from the v1 day-count
# model per the blueprint's "keep the UX untouched" instruction.
_STAGES = [
    {
        'name': 'new',
        'min_score': 0,
        'max_score': 5,
        'horizon': 0,
        'next_label': 'First week of data',
        'message': "Hi! I'm here to help you understand your cash flow. Let's start by connecting your bank account or uploading some documents.",
        'mood': 'idle',
        'capabilities': ['document_upload', 'manual_entry'],
    },
    {
        'name': 'learning',
        'min_score': 5,
        'max_score': 25,
        'horizon': 7,
        'next_label': '2 weeks of data',
        'message': "I'm learning your cash patterns! I can already see your next 7 days. Keep adding data and I'll get smarter.",
        'mood': 'thinking',
        'capabilities': ['document_upload', 'manual_entry', 'transaction_view', 'forecast_7day', 'balance_today'],
    },
    {
        'name': 'developing',
        'min_score': 25,
        'max_score': 50,
        'horizon': 30,
        'next_label': '2 months of data',
        'message': "I'm starting to recognise your patterns — recurring payments, customer timing, seasonal trends. Your 30-day forecast is ready.",
        'mood': 'happy',
        'capabilities': ['document_upload', 'manual_entry', 'transaction_view',
                         'forecast_7day', 'forecast_30day', 'balance_today',
                         'recurring_detection', 'customer_risk_basic'],
    },
    {
        'name': 'established',
        'min_score': 50,
        'max_score': 75,
        'horizon': 90,
        'next_label': '6 months of data',
        'message': "I know your business well now. I can forecast 90 days ahead with confidence and I'm tracking your FX exposure and late payment risk.",
        'mood': 'happy',
        'capabilities': ['document_upload', 'manual_entry', 'transaction_view',
                         'forecast_7day', 'forecast_30day', 'forecast_90day',
                         'balance_today', 'recurring_detection',
                         'customer_risk_full', 'fx_exposure', 'scenario_modelling',
                         'ai_daily_briefing'],
    },
    {
        'name': 'expert',
        'min_score': 75,
        'max_score': 100,
        'horizon': 365,
        'next_label': 'Full intelligence active',
        'message': "I've seen your seasonal cycles now. I can anticipate demand spikes, slow periods, and currency impacts up to a year ahead. Full intelligence active.",
        'mood': 'happy',
        'capabilities': ['document_upload', 'manual_entry', 'transaction_view',
                         'forecast_7day', 'forecast_30day', 'forecast_90day', 'forecast_365day',
                         'balance_today', 'recurring_detection',
                         'customer_risk_full', 'fx_exposure', 'scenario_modelling',
                         'ai_daily_briefing', 'seasonal_intelligence', 'annual_planning'],
    },
]

# Weights sum to 1.0 — component sub-scores are each 0-100, so the weighted
# sum is directly a 0-100 composite score.
_WEIGHT_HISTORY_SPAN = 0.30
_WEIGHT_COVERAGE_DENSITY = 0.25
_WEIGHT_CATEGORISATION_RATE = 0.15
_WEIGHT_SOURCE_RELIABILITY = 0.15
_WEIGHT_RECONCILIATION_RATE = 0.10
_WEIGHT_RECENCY = 0.05

_HISTORY_SPAN_CAP_DAYS = 365
# Recency decays linearly to 0 over this many stale days — the blueprint
# specifies the 5% weight but not a decay curve, so this is our own
# reasonable interpretation, documented here rather than left implicit.
_RECENCY_DECAY_DAYS = 30


def calculate_maturity(org_id: str) -> MaturityProfile:
    """Calculate the current composite forecast maturity for an organisation."""
    components, days_of_data = _compute_component_scores(org_id)
    score = (
        components['history_span'] * _WEIGHT_HISTORY_SPAN
        + components['coverage_density'] * _WEIGHT_COVERAGE_DENSITY
        + components['categorisation_rate'] * _WEIGHT_CATEGORISATION_RATE
        + components['source_reliability'] * _WEIGHT_SOURCE_RELIABILITY
        + components['reconciliation_rate'] * _WEIGHT_RECONCILIATION_RATE
        + components['recency'] * _WEIGHT_RECENCY
    )
    return _profile_from_score(round(score, 2), components, days_of_data)


def _compute_component_scores(org_id: str) -> tuple[ComponentScores, int]:
    from django.db.models import Max, Min

    from apps.transactions.models import Transaction

    agg = Transaction.objects.filter(org_id=org_id).aggregate(
        earliest=Min('timestamp'), latest=Max('timestamp'),
    )
    earliest, latest = agg.get('earliest'), agg.get('latest')

    if earliest is None or latest is None:
        # No transactions yet — every component is genuinely zero. (The
        # "nothing to reconcile isn't a penalty" exemption in
        # `_reconciliation_rate_score` only applies once there's at least
        # some transaction history to judge the other five components
        # against — it must not leak points into a truly empty org.)
        from apps.documents.models import Document
        doc_count = Document.objects.filter(org_id=org_id, status='confirmed').count()
        days_of_data = min(doc_count * 2, 7)
        components: ComponentScores = {
            'history_span': 0.0, 'coverage_density': 0.0, 'categorisation_rate': 0.0,
            'source_reliability': 0.0, 'reconciliation_rate': 0.0, 'recency': 0.0,
        }
        return components, days_of_data

    days_of_data = max(0, (latest.date() - earliest.date()).days + 1)

    components = {
        'history_span': _history_span_score(days_of_data),
        'coverage_density': _coverage_density_score(org_id, earliest, latest, days_of_data),
        'categorisation_rate': _categorisation_rate_score(org_id),
        'source_reliability': _source_reliability_score(org_id),
        'reconciliation_rate': _reconciliation_rate_score(org_id),
        'recency': _recency_score(latest),
    }
    return components, days_of_data


def _history_span_score(days_of_data: int) -> float:
    return round(min(days_of_data, _HISTORY_SPAN_CAP_DAYS) / _HISTORY_SPAN_CAP_DAYS * 100, 2)


def _coverage_density_score(org_id: str, earliest, latest, days_of_data: int) -> float:
    from django.db.models.functions import TruncDate

    from apps.transactions.models import Transaction

    if days_of_data <= 0:
        return 0.0

    days_with_data = (
        Transaction.objects.filter(org_id=org_id, timestamp__range=(earliest, latest))
        .annotate(day=TruncDate('timestamp'))
        .values('day')
        .distinct()
        .count()
    )
    return round(min(days_with_data / days_of_data, 1.0) * 100, 2)


def _categorisation_rate_score(org_id: str) -> float:
    from apps.transactions.models import Transaction

    total = Transaction.objects.filter(org_id=org_id).count()
    if total == 0:
        return 0.0
    categorised = Transaction.objects.filter(org_id=org_id, category__isnull=False).count()
    return round(categorised / total * 100, 2)


def _source_reliability_score(org_id: str) -> float:
    from django.db.models import Case, IntegerField, Sum, Value, When

    from apps.transactions.models import Transaction

    qs = Transaction.objects.filter(org_id=org_id)
    total = qs.count()
    if total == 0:
        return 0.0

    reliability_case = Case(
        *[When(source=src, then=Value(val)) for src, val in Transaction.SOURCE_RELIABILITY.items()],
        default=Value(0),
        output_field=IntegerField(),
    )
    total_reliability = qs.annotate(_rel=reliability_case).aggregate(total=Sum('_rel'))['total'] or 0
    return round(total_reliability / total, 2)


def _reconciliation_rate_score(org_id: str) -> float:
    from apps.counterparties.models import Invoice
    from apps.documents.models import Document

    invoices_total = Invoice.objects.filter(org_id=org_id).count()
    invoices_matched = Invoice.objects.filter(org_id=org_id, matched_transaction__isnull=False).count()

    docs_total = Document.objects.filter(org_id=org_id, status='confirmed').count()
    docs_matched = Document.objects.filter(
        org_id=org_id, status='confirmed', created_transaction_id__isnull=False,
    ).count()

    total = invoices_total + docs_total
    if total == 0:
        # Nothing to reconcile isn't a data-quality problem — don't penalise
        # cash-only orgs with no invoices/documents at all.
        return 100.0

    matched = invoices_matched + docs_matched
    return round(matched / total * 100, 2)


def _recency_score(latest) -> float:
    days_stale = max(0, (timezone.now().date() - latest.date()).days)
    return round(max(0.0, 100.0 - (days_stale * (100.0 / _RECENCY_DECAY_DAYS))), 2)


def _profile_from_score(score: float, components: ComponentScores, days_of_data: int) -> MaturityProfile:
    current_stage = _STAGES[0]
    for stage in _STAGES:
        if stage['min_score'] <= score < stage['max_score']:
            current_stage = stage
            break
    else:
        if score >= _STAGES[-1]['min_score']:
            current_stage = _STAGES[-1]

    if current_stage['name'] == 'expert':
        progress = 1.0
        next_milestone_score = 0
    else:
        span = current_stage['max_score'] - current_stage['min_score']
        elapsed = score - current_stage['min_score']
        progress = min(1.0, max(0.0, elapsed / span)) if span > 0 else 0.0
        next_milestone_score = int(round(current_stage['max_score'] - score))

    return MaturityProfile(
        stage=current_stage['name'],
        score=score,
        component_scores=components,
        days_of_data=days_of_data,
        forecast_horizon_days=current_stage['horizon'],
        progress_to_next=round(progress, 3),
        mascot_message=current_stage['message'],
        mascot_mood=current_stage['mood'],
        capabilities=current_stage['capabilities'],
        next_milestone_days=next_milestone_score,
        next_milestone_label=current_stage['next_label'],
    )
