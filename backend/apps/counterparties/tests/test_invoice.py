"""Invoice — relocated from the retired `customers` app onto Counterparty."""
from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError

from apps.counterparties.models import Counterparty, Invoice

pytestmark = pytest.mark.unit


@pytest.mark.django_db
def test_invoice_amount_is_exact_decimal(org):
    customer = Counterparty.objects.create(org=org, name='Acme Client Ltd', type=Counterparty.TYPE_CUSTOMER)
    invoice = Invoice.objects.create(
        org=org, counterparty=customer, amount=Decimal('1999.99'), currency='GBP',
        issue_date='2026-01-01', due_date='2026-01-31',
    )
    invoice.refresh_from_db()
    assert invoice.amount == Decimal('1999.99')
    assert isinstance(invoice.amount, Decimal)


@pytest.mark.django_db
def test_clean_rejects_non_customer_counterparty(org):
    supplier = Counterparty.objects.create(org=org, name='Beanwholesale Ltd', type=Counterparty.TYPE_SUPPLIER)
    invoice = Invoice(
        org=org, counterparty=supplier, amount=Decimal('100.00'), currency='GBP',
        issue_date='2026-01-01', due_date='2026-01-31',
    )
    with pytest.raises(ValidationError):
        invoice.clean()


@pytest.mark.django_db
def test_clean_allows_customer_counterparty(org):
    customer = Counterparty.objects.create(org=org, name='Acme Client Ltd', type=Counterparty.TYPE_CUSTOMER)
    invoice = Invoice(
        org=org, counterparty=customer, amount=Decimal('100.00'), currency='GBP',
        issue_date='2026-01-01', due_date='2026-01-31',
    )
    invoice.clean()  # does not raise


@pytest.mark.django_db
def test_clean_allows_null_counterparty(org):
    invoice = Invoice(
        org=org, counterparty=None, amount=Decimal('100.00'), currency='GBP',
        issue_date='2026-01-01', due_date='2026-01-31',
    )
    invoice.clean()  # does not raise
