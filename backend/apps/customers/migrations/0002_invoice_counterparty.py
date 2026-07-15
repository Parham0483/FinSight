import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('customers', '0001_initial'),
        ('counterparties', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='invoice',
            name='counterparty',
            field=models.ForeignKey(
                blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                related_name='invoices', to='counterparties.counterparty',
            ),
        ),
        migrations.AddIndex(
            model_name='invoice',
            index=models.Index(fields=['counterparty'], name='invoices_counterparty_idx'),
        ),
    ]
