"""Root pytest fixtures shared across all app test suites."""
import pytest
from rest_framework.test import APIClient

from apps.authentication.models import User
from apps.organisations.models import Organisation, OrgMembership


@pytest.fixture
def api_client() -> APIClient:
    return APIClient()


@pytest.fixture
def user(db) -> User:
    return User.objects.create_user(
        email='owner@example.com', password='pw-test-1234', full_name='Test Owner',
        is_verified=True,
    )


@pytest.fixture
def other_user(db) -> User:
    return User.objects.create_user(
        email='stranger@example.com', password='pw-test-1234', full_name='Stranger',
        is_verified=True,
    )


@pytest.fixture
def org(db) -> Organisation:
    return Organisation.objects.create(
        name='Acme Trading', industry='wholesale', country_code='GB', base_currency='GBP',
    )


@pytest.fixture
def membership(db, user, org) -> OrgMembership:
    return OrgMembership.objects.create(user=user, org=org, role='owner')


@pytest.fixture
def auth_client(api_client, user, membership) -> APIClient:
    """An APIClient authenticated as `user`, who owns `org`."""
    api_client.force_authenticate(user=user)
    return api_client
