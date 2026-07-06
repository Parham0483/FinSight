from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('documents', '0001_initial'),
    ]

    operations = [
        migrations.RenameField(
            model_name='document',
            old_name='created_customer_id',
            new_name='created_counterparty_id',
        ),
    ]
