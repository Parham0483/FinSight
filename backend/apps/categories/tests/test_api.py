import pytest

from apps.categories.models import Category
from apps.categories.seeds import seed_default_categories

pytestmark = pytest.mark.integration

LIST_URL = '/api/v1/categories/'


def test_list_requires_authentication(api_client, org):
    resp = api_client.get(f'{LIST_URL}?org={org.id}')
    assert resp.status_code == 401


def test_list_returns_seeded_categories_for_org(auth_client, org):
    seed_default_categories(org)
    resp = auth_client.get(f'{LIST_URL}?org={org.id}')

    assert resp.status_code == 200
    body = resp.json()
    assert body['success'] is True
    slugs = {row['slug'] for row in body['data']}
    assert 'expenses' in slugs and 'income' in slugs


def test_list_rejects_org_the_user_does_not_belong_to(auth_client, other_user, db):
    from apps.organisations.models import Organisation, OrgMembership

    foreign = Organisation.objects.create(name='Foreign', base_currency='EUR')
    OrgMembership.objects.create(user=other_user, org=foreign, role='owner')
    seed_default_categories(foreign)

    resp = auth_client.get(f'{LIST_URL}?org={foreign.id}')
    assert resp.status_code == 403


def test_create_custom_category(auth_client, org):
    seed_default_categories(org)
    parent = Category.objects.get(org=org, slug='expenses')

    resp = auth_client.post(LIST_URL, {
        'org': str(org.id),
        'name': 'Marketing',
        'kind': 'expense',
        'parent': str(parent.id),
    }, format='json')

    assert resp.status_code == 201
    data = resp.json()['data']
    assert data['slug'] == 'marketing'
    assert data['is_system'] is False
    created = Category.objects.get(id=data['id'])
    assert created.parent_id == parent.id
