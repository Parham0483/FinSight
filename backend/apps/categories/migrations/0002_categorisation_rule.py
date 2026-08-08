import django.db.models.deletion
import uuid
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('categories', '0001_initial'),
        ('counterparties', '0001_initial'),
        ('organisations', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='CategorisationRule',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('hit_count', models.PositiveIntegerField(default=1)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('category', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='rules', to='categories.category')),
                ('counterparty', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='categorisation_rules', to='counterparties.counterparty')),
                ('org', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='categorisation_rules', to='organisations.organisation')),
            ],
            options={
                'db_table': 'categorisation_rules',
                'unique_together': {('org', 'counterparty')},
            },
        ),
    ]
