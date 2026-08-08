"""Backfill: create a type=customer Counterparty for every Customer, then
repoint Invoice.counterparty from Invoice.customer.

Self-contained (no import of app code) so this migration's behaviour never
drifts if `apps.counterparties.models.normalise_name` changes later — data
migrations must remain reproducible independent of current model code.

Idempotent: re-running finds existing customer-typed counterparties by
(org, normalised_name) and reuses them rather than duplicating.
"""
import re

from django.db import migrations

_PROCESSOR_STOP_WORDS = frozenset({
    'pos', 'crd', 'card', 'payment', 'pmt', 'ref', 'txn',
    'visa', 'mastercard', 'paypal',
})


def _normalise_name(raw: str) -> str:
    if not raw:
        return ''
    tokens = re.split(r'[^a-z0-9]+', raw.lower())
    kept = [
        token for token in tokens
        if token and token not in _PROCESSOR_STOP_WORDS and not any(c.isdigit() for c in token)
    ]
    return ' '.join(kept)


def _provenance_note(customer) -> str:
    line = (
        f'[migrated-from-customer risk_score={customer.risk_score} '
        f'avg_days_late={customer.avg_days_late} '
        f'payment_terms_days={customer.payment_terms_days}]'
    )
    return f'{customer.notes}\n{line}'.strip() if customer.notes else line


def backfill(apps, schema_editor):
    Customer = apps.get_model('customers', 'Customer')
    Invoice = apps.get_model('customers', 'Invoice')
    Counterparty = apps.get_model('counterparties', 'Counterparty')

    customer_to_counterparty: dict = {}

    for customer in Customer.objects.all():
        key = _normalise_name(customer.name)
        counterparty = (
            Counterparty.objects.filter(org_id=customer.org_id, normalised_name=key, type='customer')
            .order_by('created_at')
            .first()
        )
        if counterparty is None:
            counterparty = Counterparty.objects.create(
                org_id=customer.org_id,
                name=customer.name,
                normalised_name=key,
                type='customer',
                email=customer.email,
                is_auto_created=False,
                notes=_provenance_note(customer),
            )
        customer_to_counterparty[customer.id] = counterparty.id

    for invoice in Invoice.objects.filter(customer__isnull=False):
        counterparty_id = customer_to_counterparty.get(invoice.customer_id)
        if counterparty_id is not None and invoice.counterparty_id != counterparty_id:
            invoice.counterparty_id = counterparty_id
            invoice.save(update_fields=['counterparty'])


def unbackfill(apps, schema_editor):
    Invoice = apps.get_model('customers', 'Invoice')
    Invoice.objects.filter(counterparty__isnull=False).update(counterparty=None)


class Migration(migrations.Migration):

    dependencies = [
        ('customers', '0002_invoice_counterparty'),
    ]

    operations = [
        migrations.RunPython(backfill, unbackfill),
    ]
