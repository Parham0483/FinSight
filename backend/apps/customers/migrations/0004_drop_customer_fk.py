from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('customers', '0003_backfill_counterparties'),
    ]

    operations = [
        migrations.RemoveIndex(
            model_name='invoice',
            name='invoices_custome_ba8289_idx',
        ),
        migrations.RemoveField(
            model_name='invoice',
            name='customer',
        ),
    ]
