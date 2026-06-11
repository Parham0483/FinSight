"""
Forecast maturity system — determines what level of intelligence is available
for an organisation based on how much data has been accumulated.

Stages progress automatically as data grows. The frontend mascot reflects
the current stage and coaches the user toward the next one.

Stages:
  new         → 0 days of data
  learning    → 1–14 days  → 7-day short-term forecast
  developing  → 15–60 days → 30-day forecast
  established → 61–180 days → 90-day forecast
  expert      → 181+ days  → Full 365-day + seasonal intelligence
"""

from dataclasses import dataclass
from datetime import date, timedelta
from typing import Optional


@dataclass(frozen=True)
class MaturityProfile:
    stage: str                  # new / learning / developing / established / expert
    days_of_data: int
    forecast_horizon_days: int  # max days the forecast will cover
    progress_to_next: float     # 0.0–1.0 toward the next stage
    mascot_message: str         # what the mascot says at this stage
    mascot_mood: str            # idle / thinking / happy / concerned
    capabilities: list[str]     # features unlocked at this stage
    next_milestone_days: int    # data days needed to reach next stage
    next_milestone_label: str


_STAGES = [
    {
        'name': 'new',
        'min_days': 0,
        'max_days': 0,
        'horizon': 0,
        'next': 1,
        'next_label': 'First week of data',
        'message': "Hi! I'm here to help you understand your cash flow. Let's start by connecting your bank account or uploading some documents.",
        'mood': 'idle',
        'capabilities': ['document_upload', 'manual_entry'],
    },
    {
        'name': 'learning',
        'min_days': 1,
        'max_days': 14,
        'horizon': 7,
        'next': 15,
        'next_label': '2 weeks of data',
        'message': "I'm learning your cash patterns! I can already see your next 7 days. Keep adding data and I'll get smarter.",
        'mood': 'thinking',
        'capabilities': ['document_upload', 'manual_entry', 'transaction_view', 'forecast_7day', 'balance_today'],
    },
    {
        'name': 'developing',
        'min_days': 15,
        'max_days': 60,
        'horizon': 30,
        'next': 61,
        'next_label': '2 months of data',
        'message': "I'm starting to recognise your patterns — recurring payments, customer timing, seasonal trends. Your 30-day forecast is ready.",
        'mood': 'happy',
        'capabilities': ['document_upload', 'manual_entry', 'transaction_view',
                         'forecast_7day', 'forecast_30day', 'balance_today',
                         'recurring_detection', 'customer_risk_basic'],
    },
    {
        'name': 'established',
        'min_days': 61,
        'max_days': 180,
        'horizon': 90,
        'next': 181,
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
        'min_days': 181,
        'max_days': 99999,
        'horizon': 365,
        'next': 99999,
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


def calculate_maturity(org_id: str) -> MaturityProfile:
    """
    Calculate the current forecast maturity for an organisation.
    Based on the span of actual transaction data available.
    """
    days = _count_data_days(org_id)
    return _profile_from_days(days)


def _count_data_days(org_id: str) -> int:
    """Count how many days of transaction history exist for this org.

    Source-agnostic: every ingestion source normalises into ``Transaction``
    with a direct ``org`` link, so one query spans bank feeds, CSV imports,
    documents, and manual entries alike.
    """
    from django.db.models import Max, Min

    from apps.transactions.models import Transaction

    result = Transaction.objects.filter(org_id=org_id).aggregate(
        earliest=Min('timestamp'),
        latest=Max('timestamp'),
    )

    earliest = result.get('earliest')
    latest = result.get('latest')

    if earliest is None or latest is None:
        # No transactions yet — fall back to confirmed documents as a weak signal.
        from apps.documents.models import Document
        doc_count = Document.objects.filter(org_id=org_id, status='confirmed').count()
        return min(doc_count * 2, 7)  # each confirmed doc = 2 notional days, cap at 7

    return max(0, (latest.date() - earliest.date()).days + 1)


def _profile_from_days(days: int) -> MaturityProfile:
    current_stage = _STAGES[0]
    for stage in _STAGES:
        if stage['min_days'] <= days <= stage['max_days']:
            current_stage = stage
            break

    # Calculate progress toward next stage
    if current_stage['name'] == 'expert':
        progress = 1.0
    else:
        span = current_stage['next'] - current_stage['min_days']
        elapsed = days - current_stage['min_days']
        progress = min(1.0, elapsed / span) if span > 0 else 0.0

    return MaturityProfile(
        stage=current_stage['name'],
        days_of_data=days,
        forecast_horizon_days=current_stage['horizon'],
        progress_to_next=round(progress, 3),
        mascot_message=current_stage['message'],
        mascot_mood=current_stage['mood'],
        capabilities=current_stage['capabilities'],
        next_milestone_days=current_stage['next'],
        next_milestone_label=current_stage['next_label'],
    )
