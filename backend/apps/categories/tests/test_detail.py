import pytest

from apps.categories.models import Category
from apps.categories.seeds import seed_default_categories

pytestmark = pytest.mark.integration


def _url(pk, org):
    return f'/api/v1/categories/{pk}/?org={org.id}'


def test_retrieve_category(auth_client, org):
    seed_default_categories(org)
    cat = Category.objects.get(org=org, slug='payroll')

    resp = auth_client.get(_url(cat.id, org))

    assert resp.status_code == 200
    assert resp.json()['data']['slug'] == 'payroll'


def test_rename_category(auth_client, org):
    seed_default_categories(org)
    cat = Category.objects.get(org=org, slug='payroll')

    resp = auth_client.patch(_url(cat.id, org), {'name': 'Staff Wages'}, format='json')

    assert resp.status_code == 200
    cat.refresh_from_db()
    assert cat.name == 'Staff Wages'
    assert cat.slug == 'payroll'  # slug is stable across renames


def test_delete_custom_category(auth_client, org):
    seed_default_categories(org)
    custom = Category.objects.create(org=org, name='Travel', kind=Category.KIND_EXPENSE)

    resp = auth_client.delete(_url(custom.id, org))

    assert resp.status_code == 204
    assert not Category.objects.filter(id=custom.id).exists()


def test_system_category_cannot_be_deleted(auth_client, org):
    seed_default_categories(org)
    system = Category.objects.get(org=org, slug='payroll')

    resp = auth_client.delete(_url(system.id, org))

    assert resp.status_code == 409
    assert Category.objects.filter(id=system.id).exists()


def test_retrieve_missing_category_returns_404(auth_client, org):
    import uuid

    resp = auth_client.get(_url(uuid.uuid4(), org))
    assert resp.status_code == 404
