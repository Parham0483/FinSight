import pytest


@pytest.mark.integration
def test_membership_fixture_wires_user_to_org(membership, user, org):
    assert membership.user == user
    assert membership.org == org
    assert membership.role == "owner"
