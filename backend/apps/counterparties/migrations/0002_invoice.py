"""State-only pickup of Invoice from `customers` (see
customers/migrations/0005_move_invoice_to_counterparties). No database
operations — the `invoices` table already exists from the old app's schema
migrations; this just registers it under `counterparties` in Django's model
state going forward.
"""
import django.db.models.deletion
import uuid
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('counterparties', '0001_initial'),
        ('customers', '0005_move_invoice_to_counterparties'),
        ('transactions', '0001_initial'),
        ('organisations', '0001_initial'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.CreateModel(
                    name='Invoice',
                    fields=[
                        ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                        ('reference', models.CharField(blank=True, max_length=100)),
                        ('amount', models.DecimalField(decimal_places=2, max_digits=15)),
                        ('currency', models.CharField(default='GBP', max_length=3)),
                        ('issue_date', models.DateField()),
                        ('due_date', models.DateField()),
                        ('paid_date', models.DateField(blank=True, null=True)),
                        ('status', models.CharField(choices=[('unpaid', 'Unpaid'), ('partial', 'Partially Paid'), ('paid', 'Paid'), ('overdue', 'Overdue'), ('written_off', 'Written Off')], default='unpaid', max_length=50)),
                        ('notes', models.TextField(blank=True)),
                        ('created_at', models.DateTimeField(auto_now_add=True)),
                        ('counterparty', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='invoices', to='counterparties.counterparty')),
                        ('matched_transaction', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='matched_invoices', to='transactions.transaction')),
                        ('org', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='invoices', to='organisations.organisation')),
                    ],
                    options={
                        'db_table': 'invoices',
                        'indexes': [
                            models.Index(fields=['status', 'due_date'], name='invoices_status_73cf28_idx'),
                            models.Index(fields=['counterparty'], name='invoices_counterparty_idx'),
                        ],
                    },
                ),
            ],
            database_operations=[],
        ),
    ]
