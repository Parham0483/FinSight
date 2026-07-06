"""Fuzzy-matcher generalisation: Counterparty replaces the old Customer target,
matched across all types (not just customer) since document vendors/payees are
frequently suppliers, not customers.
"""
import pytest

from apps.counterparties.models import Counterparty
from apps.documents.services.matching import _match_counterparty, find_matches

pytestmark = pytest.mark.unit


@pytest.mark.django_db
def test_matches_across_all_counterparty_types(org):
    Counterparty.objects.create(org=org, name='Beanwholesale Ltd', type=Counterparty.TYPE_SUPPLIER)

    counterparty_id, name, score = _match_counterparty(str(org.id), 'Beanwholesale Ltd')

    assert name == 'Beanwholesale Ltd'
    assert score == 100.0


@pytest.mark.django_db
def test_excludes_soft_merged_counterparties(org):
    survivor = Counterparty.objects.create(org=org, name='Acme Client Ltd', type=Counterparty.TYPE_CUSTOMER)
    merged = Counterparty.objects.create(org=org, name='Acme Client Limited', type=Counterparty.TYPE_CUSTOMER)
    merged.merged_into = survivor
    merged.save(update_fields=['merged_into'])

    counterparty_id, name, score = _match_counterparty(str(org.id), 'Acme Client Limited')

    # The merged row is excluded; the fuzzy match falls through to the survivor.
    assert counterparty_id == str(survivor.id)


@pytest.mark.django_db
def test_empty_directory_returns_no_match(org):
    counterparty_id, name, score = _match_counterparty(str(org.id), 'Anyone')
    assert (counterparty_id, name, score) == (None, None, 0.0)


@pytest.mark.django_db
def test_find_matches_below_threshold_suggests_nothing(org):
    Counterparty.objects.create(org=org, name='Totally Unrelated Party', type=Counterparty.TYPE_OTHER)

    suggestion = find_matches(
        org_id=str(org.id),
        extracted_data={'vendor_name': 'Zzz Nonmatching Vendor Name Co'},
        document_type='invoice',
    )

    assert suggestion.counterparty_id is None
    assert suggestion.counterparty_match_score < 75


@pytest.mark.django_db
def test_find_matches_above_threshold_suggests_counterparty(org):
    cp = Counterparty.objects.create(org=org, name='Dairy Direct', type=Counterparty.TYPE_SUPPLIER)

    suggestion = find_matches(
        org_id=str(org.id),
        extracted_data={'vendor_name': 'Dairy Direct'},
        document_type='invoice',
    )

    assert suggestion.counterparty_id == str(cp.id)
    assert suggestion.counterparty_match_score == 100.0
