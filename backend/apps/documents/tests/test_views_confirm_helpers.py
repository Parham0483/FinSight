"""`_create_counterparty` / `_create_invoice` — the document-confirm flow now
routes through `resolve_counterparty` (canonical-key dedup) instead of a bare
Customer.get_or_create, and Invoice is filtered to type=customer per the
Invoice.clean() convention. Flagged by the phase-boundary audit as new
merge-adjacent logic with no direct coverage.
"""
from decimal import Decimal

import pytest

from apps.counterparties.models import Counterparty, Invoice
from apps.documents.views import _create_counterparty, _create_invoice

pytestmark = pytest.mark.unit


@pytest.mark.django_db
def test_create_counterparty_dedupes_against_existing_entry(org):
    existing = Counterparty.objects.create(
        org=org, name='Acme Client Ltd', type=Counterparty.TYPE_SUPPLIER,
    )

    counterparty_id = _create_counterparty(
        org, {'vendor_name': 'Acme Client Ltd.'}, 'invoice',  # trailing period — same canonical key
    )

    assert counterparty_id == str(existing.id)
    assert Counterparty.objects.filter(org=org).count() == 1


@pytest.mark.django_db
def test_create_counterparty_creates_new_when_no_match(org):
    counterparty_id = _create_counterparty(org, {'vendor_name': 'Brand New Vendor Co'}, 'invoice')

    cp = Counterparty.objects.get(id=counterparty_id)
    assert cp.name == 'Brand New Vendor Co'
    assert cp.type == Counterparty.TYPE_CUSTOMER


@pytest.mark.django_db
def test_create_counterparty_blank_name_returns_none(org):
    assert _create_counterparty(org, {}, 'invoice') is None


@pytest.mark.django_db
def test_create_invoice_links_customer_type_counterparty(org):
    customer = Counterparty.objects.create(org=org, name='Acme Client Ltd', type=Counterparty.TYPE_CUSTOMER)

    invoice_id = _create_invoice(
        org,
        {'total_amount': '499.99', 'invoice_number': 'INV-9', 'issue_date': '2026-01-01', 'due_date': '2026-01-31'},
        'invoice',
        str(customer.id),
    )

    invoice = Invoice.objects.get(id=invoice_id)
    assert invoice.counterparty_id == customer.id
    assert invoice.amount == Decimal('499.99')


@pytest.mark.django_db
def test_create_invoice_ignores_non_customer_counterparty_id(org):
    supplier = Counterparty.objects.create(org=org, name='Beanwholesale Ltd', type=Counterparty.TYPE_SUPPLIER)

    invoice_id = _create_invoice(
        org,
        {'total_amount': '10.00', 'issue_date': '2026-01-01', 'due_date': '2026-01-31'},
        'invoice',
        str(supplier.id),
    )

    invoice = Invoice.objects.get(id=invoice_id)
    assert invoice.counterparty_id is None


@pytest.mark.django_db
def test_create_invoice_no_amount_returns_none(org):
    assert _create_invoice(org, {}, 'invoice', None) is None
