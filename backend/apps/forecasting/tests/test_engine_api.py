"""CombinedForecastView — the API surface over engine/combined.py's tested math.
Risk-based smoke coverage: the underlying computation is already exhaustively
tested in engine/tests/; this checks the HTTP contract (auth, org isolation,
query param validation, response shape) rather than re-deriving the numbers.
"""
from datetime import timedelta
from decimal import Decimal

import pytest
from django.utils import timezone

from apps.transactions.models import Transaction

pytestmark = pytest.mark.unit


def _seed_history(org, days=40):
    for i in range(days):
        amount = Decimal('100.00') if i % 2 == 0 else Decimal('-30.00')
        Transaction.objects.create(
            org=org, source=Transaction.SOURCE_MANUAL,
            timestamp=timezone.now() - timedelta(days=days - i),
            amount=amount, currency=org.base_currency,
            base_amount=amount, base_currency=org.base_currency,
        )


@pytest.mark.django_db
class TestCombinedForecastView:
    def test_requires_auth(self, api_client, org):
        resp = api_client.get(f'/api/v1/forecast/orgs/{org.id}/combined/')
        assert resp.status_code == 401

    def test_denies_non_member(self, auth_client, org, other_user):
        from apps.organisations.models import Organisation
        other_org = Organisation.objects.create(name='Other Org', base_currency='USD')
        resp = auth_client.get(f'/api/v1/forecast/orgs/{other_org.id}/combined/')
        assert resp.status_code == 403

    def test_returns_envelope_shape(self, auth_client, org):
        _seed_history(org)
        resp = auth_client.get(f'/api/v1/forecast/orgs/{org.id}/combined/?horizon_days=7')
        assert resp.status_code == 200
        data = resp.json()['data']
        assert 'starting_balance' in data
        assert 'horizon_days' in data
        assert data['horizon_days'] == 7
        assert 'points' in data
        assert len(data['points']) == 7
        assert 'runway' in data
        assert 'driver_totals' in data
        point = data['points'][0]
        for field in ('date', 'known_net', 'statistical_p10', 'statistical_p50',
                      'statistical_p90', 'balance_p10', 'balance_p50', 'balance_p90', 'drivers'):
            assert field in point

    def test_bands_are_ordered_in_response(self, auth_client, org):
        _seed_history(org)
        resp = auth_client.get(f'/api/v1/forecast/orgs/{org.id}/combined/?horizon_days=5')
        for point in resp.json()['data']['points']:
            assert Decimal(point['balance_p10']) <= Decimal(point['balance_p50']) <= Decimal(point['balance_p90'])

    def test_no_history_still_returns_layer1_only_projection(self, auth_client, org):
        # A brand-new org (no transactions) must not error — falls back to
        # Layer 1 alone, per engine/combined.py's documented behaviour.
        resp = auth_client.get(f'/api/v1/forecast/orgs/{org.id}/combined/?horizon_days=5')
        assert resp.status_code == 200
        assert len(resp.json()['data']['points']) == 5

    def test_invalid_horizon_days_rejected(self, auth_client, org):
        resp = auth_client.get(f'/api/v1/forecast/orgs/{org.id}/combined/?horizon_days=not-a-number')
        assert resp.status_code == 400

    def test_negative_horizon_days_rejected(self, auth_client, org):
        resp = auth_client.get(f'/api/v1/forecast/orgs/{org.id}/combined/?horizon_days=-5')
        assert resp.status_code == 400

    def test_invalid_safety_buffer_rejected(self, auth_client, org):
        resp = auth_client.get(
            f'/api/v1/forecast/orgs/{org.id}/combined/?horizon_days=5&safety_buffer=not-a-decimal'
        )
        assert resp.status_code == 400

    def test_default_horizon_days_comes_from_maturity_stage(self, auth_client, org):
        # No history at all -> 'new' stage -> maturity horizon is 0, which the
        # view must not pass straight through as an invalid/zero-length
        # forecast — it falls back to a sane default (30).
        resp = auth_client.get(f'/api/v1/forecast/orgs/{org.id}/combined/')
        assert resp.status_code == 200
        assert resp.json()['data']['horizon_days'] == 30
