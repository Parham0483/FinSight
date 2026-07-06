from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('customers', '0005_move_invoice_to_counterparties'),
    ]

    operations = [
        migrations.DeleteModel(name='Customer'),
    ]
