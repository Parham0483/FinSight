import pytest

from apps.counterparties.models import Counterparty
from apps.counterparties.services import merge_counterparties, resolve_counterparty


@pytest.mark.django_db
def test_resolve_creates_auto_counterparty(org):
    cp = resolve_counterparty(org, 'AMZN*MKTP UK')
    assert cp is not None
    assert cp.is_auto_created is True
    assert cp.normalised_name == 'amzn mktp uk'


@pytest.mark.django_db
def test_resolve_matches_existing_by_key(org):
    first = resolve_counterparty(org, 'AMZN*MKTP UK*123')
    second = resolve_counterparty(org, 'AMZN MKTP UK')
    assert first.id == second.id  # same canonical key → same entity


@pytest.mark.django_db
def test_resolve_blank_name_returns_none(org):
    assert resolve_counterparty(org, '   ') is None
    assert resolve_counterparty(org, '#REF') is None


@pytest.mark.django_db
def test_resolve_follows_merge_chain(org):
    survivor = Counterparty.objects.create(org=org, name='Amazon', normalised_name='amazon')
    dupe = Counterparty.objects.create(
        org=org, name='Amazon Dupe', normalised_name='amazon dupe', merged_into=survivor,
    )
    resolved = resolve_counterparty(org, 'Amazon Dupe')
    assert resolved.id == survivor.id


@pytest.mark.django_db
def test_merge_repoints_transactions(org):
    from apps.transactions.ingestion import ManualEntrySource

    source = Counterparty.objects.create(org=org, name='Acme', normalised_name='acme', tags=['vip'])
    target = Counterparty.objects.create(org=org, name='Acme Corp', normalised_name='acme corp', tags=['key'])

    # Create a transaction linked to source via the manual ingestion pipeline.
    ManualEntrySource(org, entries=[{
        'timestamp': '2026-01-01T10:00:00Z', 'amount': '100.00',
        'currency': 'GBP', 'counterparty_name': 'Acme',
    }]).sync()

    merge_counterparties(source, target)
    target.refresh_from_db()
    source.refresh_from_db()

    assert source.merged_into_id == target.id
    assert set(target.tags) == {'vip', 'key'}
    assert target.transactions.count() == 1
    assert source.transactions.count() == 0


@pytest.mark.django_db
def test_merge_cross_org_rejected(org, other_user):
    from apps.organisations.models import Organisation

    other_org = Organisation.objects.create(name='Other', base_currency='USD')
    a = Counterparty.objects.create(org=org, name='A')
    b = Counterparty.objects.create(org=other_org, name='B')
    with pytest.raises(ValueError):
        merge_counterparties(a, b)


@pytest.mark.django_db
def test_merge_self_is_noop(org):
    cp = Counterparty.objects.create(org=org, name='A')
    assert merge_counterparties(cp, cp).id == cp.id
