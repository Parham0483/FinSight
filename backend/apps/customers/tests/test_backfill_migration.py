"""Risk-based coverage for the Customer -> Counterparty backfill migration
(money-handling skill: money/decimal carryover, migration idempotency).

Runs the real migration executor against an isolated test database: migrate
to just before the backfill, insert Customer/Invoice fixture rows via the
historical model state, migrate forward through the backfill, and assert
correctness. This is the only way to exercise `RunPython` migration code
once the models it references (`Customer`) no longer exist in current code.
"""
from decimal import Decimal

import pytest
from django.db.migrations.executor import MigrationExecutor
from django.db import connection

from apps.organisations.models import Organisation

pytestmark = pytest.mark.integration


def _migrate_to(target):
    executor = MigrationExecutor(connection)
    executor.migrate(target)
    executor.loader.build_graph()
    return executor


@pytest.fixture
def org(db) -> Organisation:
    return Organisation.objects.create(
        name='Acme Trading', industry='wholesale', country_code='GB', base_currency='GBP',
    )


@pytest.mark.django_db(transaction=True)
def test_backfill_creates_counterparty_and_repoints_invoice(org):
    # Land on the schema state right after the FK is added, before the backfill runs.
    executor = _migrate_to([('customers', '0002_invoice_counterparty')])
    apps = executor.loader.project_state([('customers', '0002_invoice_counterparty')]).apps
    Customer = apps.get_model('customers', 'Customer')
    Invoice = apps.get_model('customers', 'Invoice')

    customer = Customer.objects.create(
        org_id=org.id, name='Acme Client Ltd', email='ap@acmeclient.test',
        payment_terms_days=45, risk_score='amber', avg_days_late=Decimal('4.5'),
        notes='Prefers email invoices.',
    )
    invoice = Invoice.objects.create(
        org_id=org.id, customer=customer, reference='INV-100',
        amount=Decimal('1234.56'), currency='GBP',
        issue_date='2026-01-01', due_date='2026-01-31',
    )
    invoice_no_customer = Invoice.objects.create(
        org_id=org.id, customer=None, reference='INV-101',
        amount=Decimal('50.00'), currency='GBP',
        issue_date='2026-01-01', due_date='2026-01-31',
    )

    # Run the backfill (and everything after it).
    executor = _migrate_to([('customers', '0006_delete_customer'), ('counterparties', '0002_invoice')])
    apps = executor.loader.project_state(
        [('customers', '0006_delete_customer'), ('counterparties', '0002_invoice')]
    ).apps
    Counterparty = apps.get_model('counterparties', 'Counterparty')
    Invoice2 = apps.get_model('counterparties', 'Invoice')

    counterparties = list(Counterparty.objects.filter(org_id=org.id, type='customer'))
    assert len(counterparties) == 1
    cp = counterparties[0]
    assert cp.name == 'Acme Client Ltd'
    assert cp.email == 'ap@acmeclient.test'
    assert 'risk_score=amber' in cp.notes
    assert 'avg_days_late=4.5' in cp.notes
    assert 'payment_terms_days=45' in cp.notes
    assert 'Prefers email invoices.' in cp.notes

    migrated_invoice = Invoice2.objects.get(reference='INV-100')
    assert migrated_invoice.counterparty_id == cp.id
    assert migrated_invoice.amount == Decimal('1234.56')  # exact Decimal, no float coercion

    unlinked_invoice = Invoice2.objects.get(reference='INV-101')
    assert unlinked_invoice.counterparty_id is None
