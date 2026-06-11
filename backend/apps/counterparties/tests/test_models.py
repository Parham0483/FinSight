import pytest

from apps.counterparties.models import Counterparty, normalise_name


@pytest.mark.parametrize('raw,expected', [
    ('AMZN*MKTP UK*1A2B3', 'amzn mktp uk'),
    ('AMAZON.CO.UK', 'amazon co uk'),
    ('POS 1234567 TESCO STORES', 'tesco stores'),
    ('  Acme   Trading   Ltd ', 'acme trading ltd'),
    ('', ''),
    ('#REF999', ''),
])
def test_normalise_name(raw, expected):
    assert normalise_name(raw) == expected


@pytest.mark.django_db
def test_save_populates_normalised_name(org):
    cp = Counterparty.objects.create(org=org, name='AMZN*MKTP')
    assert cp.normalised_name == 'amzn mktp'


@pytest.mark.django_db
def test_explicit_normalised_name_preserved(org):
    cp = Counterparty.objects.create(org=org, name='Whatever', normalised_name='custom-key')
    assert cp.normalised_name == 'custom-key'


@pytest.mark.django_db
def test_is_merged_property(org):
    survivor = Counterparty.objects.create(org=org, name='Amazon')
    dupe = Counterparty.objects.create(org=org, name='Amazon UK', merged_into=survivor)
    assert dupe.is_merged is True
    assert survivor.is_merged is False
