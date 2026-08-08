"""State-only move: Invoice becomes a `counterparties` app model.

No database operations here — the `invoices` table is untouched. This just
tells Django's migration state that `customers` no longer owns the Invoice
model; `apps.counterparties.migrations.0002_invoice` picks it up on the other
side. The `customers` app remains registered solely to keep this migration
history valid (Django has no clean way to fully delete an app mid-lineage
while relocating one of its models to another app without breaking either
fresh installs or already-migrated databases).
"""
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('customers', '0004_drop_customer_fk'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.DeleteModel(name='Invoice'),
            ],
            database_operations=[],
        ),
    ]
