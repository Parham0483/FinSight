import pytest

from apps.counterparties.models import Counterparty


@pytest.mark.django_db
class TestCounterpartyApi:
    def test_requires_auth(self, api_client, org):
        resp = api_client.get(f'/api/v1/counterparties/?org={org.id}')
        assert resp.status_code == 401

    def test_list_empty(self, auth_client, org):
        resp = auth_client.get(f'/api/v1/counterparties/?org={org.id}')
        assert resp.status_code == 200
        assert resp.data['data'] == []

    def test_create_and_list(self, auth_client, org):
        resp = auth_client.post(
            f'/api/v1/counterparties/?org={org.id}',
            {'name': 'Acme Ltd', 'type': 'customer', 'tags': ['wholesale']},
            format='json',
        )
        assert resp.status_code == 201
        assert resp.data['data']['name'] == 'Acme Ltd'
        assert resp.data['data']['is_auto_created'] is False
        assert resp.data['data']['normalised_name'] == 'acme ltd'

        listed = auth_client.get(f'/api/v1/counterparties/?org={org.id}')
        assert len(listed.data['data']) == 1

    def test_filter_by_type(self, auth_client, org):
        Counterparty.objects.create(org=org, name='A', type='customer')
        Counterparty.objects.create(org=org, name='B', type='supplier')
        resp = auth_client.get(f'/api/v1/counterparties/?org={org.id}&type=supplier')
        assert len(resp.data['data']) == 1
        assert resp.data['data'][0]['name'] == 'B'

    def test_filter_by_tag(self, auth_client, org):
        Counterparty.objects.create(org=org, name='A', tags=['dubai'])
        Counterparty.objects.create(org=org, name='B', tags=['london'])
        resp = auth_client.get(f'/api/v1/counterparties/?org={org.id}&tag=dubai')
        assert len(resp.data['data']) == 1
        assert resp.data['data'][0]['name'] == 'A'

    def test_search_by_name(self, auth_client, org):
        Counterparty.objects.create(org=org, name='Globex Corp')
        Counterparty.objects.create(org=org, name='Initech')
        resp = auth_client.get(f'/api/v1/counterparties/?org={org.id}&search=glob')
        assert len(resp.data['data']) == 1

    def test_patch_retype(self, auth_client, org):
        cp = Counterparty.objects.create(org=org, name='A', type='other')
        resp = auth_client.patch(
            f'/api/v1/counterparties/{cp.id}/?org={org.id}',
            {'type': 'lender'}, format='json',
        )
        assert resp.status_code == 200
        cp.refresh_from_db()
        assert cp.type == 'lender'

    def test_delete(self, auth_client, org):
        cp = Counterparty.objects.create(org=org, name='A')
        resp = auth_client.delete(f'/api/v1/counterparties/{cp.id}/?org={org.id}')
        assert resp.status_code == 204
        assert not Counterparty.objects.filter(id=cp.id).exists()

    def test_org_isolation(self, auth_client, org, other_user):
        from apps.organisations.models import Organisation
        stranger_org = Organisation.objects.create(name='Stranger Org', base_currency='USD')
        cp = Counterparty.objects.create(org=stranger_org, name='Secret')
        # auth_client's user is not a member of stranger_org → 404 on org resolution.
        resp = auth_client.get(f'/api/v1/counterparties/{cp.id}/?org={stranger_org.id}')
        assert resp.status_code in (403, 404)

    def test_merged_hidden_by_default(self, auth_client, org):
        survivor = Counterparty.objects.create(org=org, name='Survivor')
        Counterparty.objects.create(org=org, name='Dupe', merged_into=survivor)
        resp = auth_client.get(f'/api/v1/counterparties/?org={org.id}')
        names = {c['name'] for c in resp.data['data']}
        assert names == {'Survivor'}
        # include_merged=true reveals it
        resp2 = auth_client.get(f'/api/v1/counterparties/?org={org.id}&include_merged=true')
        assert len(resp2.data['data']) == 2

    def test_merge_endpoint(self, auth_client, org):
        source = Counterparty.objects.create(org=org, name='Acme')
        target = Counterparty.objects.create(org=org, name='Acme Corp')
        resp = auth_client.post(
            f'/api/v1/counterparties/{source.id}/merge/?org={org.id}',
            {'target': str(target.id)}, format='json',
        )
        assert resp.status_code == 200
        source.refresh_from_db()
        assert source.merged_into_id == target.id

    def test_merge_into_self_rejected(self, auth_client, org):
        cp = Counterparty.objects.create(org=org, name='Acme')
        resp = auth_client.post(
            f'/api/v1/counterparties/{cp.id}/merge/?org={org.id}',
            {'target': str(cp.id)}, format='json',
        )
        assert resp.status_code == 400
