"""The 'solo_trader' learning_preset is calibrated against the real calculate_maturity
formula (see PROFILES comment in generate_synthetic_org.py) — this is the risk-relevant
test: if the calibration drifts (e.g. someone adds a category or extra transaction), the
demo silently stops landing in the 'learning' stage it's meant to exercise for Layer 3.
"""
from io import StringIO

import pytest
from django.core.management import call_command

from apps.forecasting.maturity import calculate_maturity
from apps.organisations.models import Organisation
from apps.transactions.models import Transaction

pytestmark = pytest.mark.unit


@pytest.mark.django_db
def test_solo_trader_preset_lands_in_learning_stage():
    call_command('generate_synthetic_org', profile='solo_trader', seed=42, name='Test Solo Trader', stdout=StringIO())

    org = Organisation.objects.get(name='Test Solo Trader')
    profile = calculate_maturity(str(org.id))
    assert profile.stage == 'learning'
    assert 5 <= profile.score < 25


@pytest.mark.django_db
def test_solo_trader_preset_creates_four_uncategorised_manual_transactions():
    call_command('generate_synthetic_org', profile='solo_trader', seed=1, name='Test Solo Trader 2', stdout=StringIO())

    org = Organisation.objects.get(name='Test Solo Trader 2')
    txns = Transaction.objects.filter(org=org)
    assert txns.count() == 4
    assert all(t.category_id is None for t in txns)
    assert all(t.source == Transaction.SOURCE_MANUAL for t in txns)


@pytest.mark.django_db
def test_solo_trader_preset_ignores_days_argument():
    call_command(
        'generate_synthetic_org', profile='solo_trader', days=365, seed=7,
        name='Test Solo Trader 3', stdout=StringIO(),
    )
    org = Organisation.objects.get(name='Test Solo Trader 3')
    assert Transaction.objects.filter(org=org).count() == 4


@pytest.mark.django_db
def test_solo_trader_preset_deterministic_across_seeds():
    """Day placement is fixed regardless of --seed; only amounts/customer choice vary."""
    for seed in (1, 2, 3, 100, 999):
        call_command(
            'generate_synthetic_org', profile='solo_trader', seed=seed,
            name=f'Test Seed {seed}', stdout=StringIO(),
        )
        org = Organisation.objects.get(name=f'Test Seed {seed}')
        profile = calculate_maturity(str(org.id))
        assert profile.stage == 'learning', f'seed {seed} did not land in learning stage'
