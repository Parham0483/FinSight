"""DataMaturity composite scorer (blueprint v2.2 §2.1) — six weighted
components, not a single day-count. Each test isolates one component so a
regression in one doesn't get masked by the others compensating.
"""
from datetime import timedelta
from decimal import Decimal

import pytest
from django.utils import timezone

from apps.categories.models import Category
from apps.categories.seeds import seed_default_categories
from apps.counterparties.models import Counterparty, Invoice
from apps.documents.models import Document
from apps.forecasting.maturity import calculate_maturity
from apps.organisations.models import Organisation
from apps.transactions.models import Transaction

pytestmark = pytest.mark.unit


def _make_txn(org, *, days_ago, source=Transaction.SOURCE_MANUAL, category=None, amount=Decimal('10.00')):
    return Transaction.objects.create(
        org=org,
        source=source,
        timestamp=timezone.now() - timedelta(days=days_ago),
        amount=amount,
        currency=org.base_currency,
        category=category,
    )


@pytest.mark.django_db
def test_no_data_scores_zero_and_stage_new(org):
    profile = calculate_maturity(str(org.id))
    assert profile.score == 0.0
    assert profile.stage == 'new'
    assert profile.component_scores['history_span'] == 0.0
    assert profile.component_scores['coverage_density'] == 0.0


@pytest.mark.django_db
def test_history_span_component_caps_at_365_days(org):
    _make_txn(org, days_ago=400)  # earliest, beyond the 365-day cap
    _make_txn(org, days_ago=0)    # latest, today
    profile = calculate_maturity(str(org.id))
    # span is 401 days but the component caps the credit at 365/365 = 100
    assert profile.component_scores['history_span'] == 100.0


@pytest.mark.django_db
def test_history_span_component_uncapped_partial(org):
    _make_txn(org, days_ago=100)
    _make_txn(org, days_ago=0)
    profile = calculate_maturity(str(org.id))
    assert profile.component_scores['history_span'] == pytest.approx(101 / 365 * 100, abs=0.1)


@pytest.mark.django_db
def test_coverage_density_penalises_gaps(org):
    # 11-day span, but only 2 of those days actually have a transaction —
    # a sparse ledger should score far below a dense one of the same span.
    _make_txn(org, days_ago=10)
    _make_txn(org, days_ago=0)
    profile = calculate_maturity(str(org.id))
    assert profile.component_scores['coverage_density'] == pytest.approx(2 / 11 * 100, abs=0.1)


@pytest.mark.django_db
def test_coverage_density_full_when_every_day_has_data(org):
    for i in range(5):
        _make_txn(org, days_ago=i)
    profile = calculate_maturity(str(org.id))
    assert profile.component_scores['coverage_density'] == 100.0


@pytest.mark.django_db
def test_categorisation_rate_component(org):
    seed_default_categories(org)
    tax = Category.objects.get(org=org, slug='tax')
    _make_txn(org, days_ago=1, category=tax)
    _make_txn(org, days_ago=0, category=None)
    profile = calculate_maturity(str(org.id))
    assert profile.component_scores['categorisation_rate'] == 50.0


@pytest.mark.django_db
def test_source_reliability_component_reflects_bank_feed_vs_manual(org):
    _make_txn(org, days_ago=1, source=Transaction.SOURCE_BANK_FEED)  # reliability 100
    _make_txn(org, days_ago=0, source=Transaction.SOURCE_MANUAL)     # reliability 40
    profile = calculate_maturity(str(org.id))
    assert profile.component_scores['source_reliability'] == pytest.approx((100 + 40) / 2, abs=0.01)


@pytest.mark.django_db
def test_reconciliation_rate_no_invoices_or_documents_defaults_full(org):
    _make_txn(org, days_ago=1)
    profile = calculate_maturity(str(org.id))
    assert profile.component_scores['reconciliation_rate'] == 100.0


@pytest.mark.django_db
def test_reconciliation_rate_reflects_matched_invoices(org):
    _make_txn(org, days_ago=1)
    customer = Counterparty.objects.create(org=org, name='Acme Client Ltd', type=Counterparty.TYPE_CUSTOMER)
    matched_txn = _make_txn(org, days_ago=0)
    Invoice.objects.create(
        org=org, counterparty=customer, amount=Decimal('500.00'), currency='GBP',
        issue_date='2026-01-01', due_date='2026-01-31', matched_transaction=matched_txn,
    )
    Invoice.objects.create(
        org=org, counterparty=customer, amount=Decimal('100.00'), currency='GBP',
        issue_date='2026-01-01', due_date='2026-01-31',
    )
    profile = calculate_maturity(str(org.id))
    assert profile.component_scores['reconciliation_rate'] == 50.0


@pytest.mark.django_db
def test_recency_decays_for_stale_data(org):
    _make_txn(org, days_ago=15)
    profile = calculate_maturity(str(org.id))
    assert profile.component_scores['recency'] == pytest.approx(100.0 - (15 * 100 / 30), abs=0.1)


@pytest.mark.django_db
def test_recency_full_for_fresh_data(org):
    _make_txn(org, days_ago=0)
    profile = calculate_maturity(str(org.id))
    assert profile.component_scores['recency'] == 100.0


@pytest.mark.django_db
def test_fast_forward_bulk_bank_history_reaches_established_immediately(org):
    """Blueprint's explicit fast-forward rule: importing 2 years of clean,
    categorised bank history on day one should jump straight past
    learning/developing, not require calendar time to pass."""
    seed_default_categories(org)
    other_income = Category.objects.get(org=org, slug='other_income')
    for i in range(0, 400, 3):  # dense coverage across the full span
        _make_txn(org, days_ago=i, source=Transaction.SOURCE_BANK_FEED, category=other_income)

    profile = calculate_maturity(str(org.id))

    assert profile.stage in ('established', 'expert')
    assert profile.score >= 50.0


@pytest.mark.django_db
def test_sparse_uncategorised_ledger_does_not_reach_expert_from_span_alone(org):
    """The exact v1 flaw the rework fixes: 3 transactions spanning 181 days
    should NOT rate 'expert' just because the calendar span is long."""
    _make_txn(org, days_ago=181, source=Transaction.SOURCE_MANUAL, category=None)
    _make_txn(org, days_ago=90, source=Transaction.SOURCE_MANUAL, category=None)
    _make_txn(org, days_ago=0, source=Transaction.SOURCE_MANUAL, category=None)

    profile = calculate_maturity(str(org.id))

    assert profile.stage not in ('expert', 'established')
    assert profile.component_scores['coverage_density'] < 5  # 3 days out of 182


@pytest.mark.django_db
def test_calculate_maturity_against_realistic_synthetic_org_does_not_crash_and_stays_sane(db):
    """Every other test in this file is a small, hand-placed fixture (1-134
    transactions). None of them exercise the scorer against the volume/shape
    of data a real org actually produces — a silent regression against
    realistic data (e.g. a query that breaks on hundreds of rows, or a
    component that goes out of [0, 100] under real seasonal patterns) would
    ship undetected. This runs the real `generate_synthetic_org` command
    (fixed seed — deterministic, not a flake) and sanity-checks the result
    rather than hand-computing an exact score, which isn't feasible for
    realistic data the way it is for the minimal fixtures above.

    `generate_synthetic_org` always creates its own new Organisation (it has
    no "target this org" option) — so this test uses whatever org the
    command creates, not the shared `org` fixture. The org name is passed
    explicitly via `--name` rather than relying on the profile's internal
    default ('Corner Café') — that default is an implementation detail of
    the café profile, not a contract this test should depend on.
    """
    from django.core.management import call_command

    synthetic_org_name = 'Realistic Maturity Test Org'
    call_command('generate_synthetic_org', profile='cafe', days=200, seed=42, name=synthetic_org_name)
    synthetic_org = Organisation.objects.get(name=synthetic_org_name)

    profile = calculate_maturity(str(synthetic_org.id))

    assert 0.0 <= profile.score <= 100.0
    assert profile.stage in ('new', 'learning', 'developing', 'established', 'expert')

    for component_name, value in profile.component_scores.items():
        assert 0.0 <= value <= 100.0, f'{component_name} out of bounds: {value}'

    # Stage must be internally consistent with the score that produced it.
    stage_score_ranges = {
        'new': (0, 5), 'learning': (5, 25), 'developing': (25, 50),
        'established': (50, 75), 'expert': (75, 100),
    }
    low, high = stage_score_ranges[profile.stage]
    assert low <= profile.score < high or (profile.stage == 'expert' and profile.score >= 75)
