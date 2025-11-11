# Generated manually for StampMetadata model

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('registry', '0058_add_sog_tco_actions'),
    ]

    operations = [
        migrations.CreateModel(
            name='StampMetadata',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('provider', models.CharField(db_index=True, help_text='The provider name that matches the stamp provider field', max_length=100, unique=True)),
                ('is_beta', models.BooleanField(default=False, help_text='Whether this stamp should display a beta badge in the UI')),
            ],
            options={
                'verbose_name': 'Stamp Metadata',
                'verbose_name_plural': 'Stamp Metadata',
                'ordering': ['provider'],
            },
        ),
        migrations.AddField(
            model_name='weightconfigurationitem',
            name='stamp_metadata',
            field=models.ForeignKey(blank=True, help_text='Link to stamp metadata (Phase 2: will become required)', null=True, on_delete=django.db.models.deletion.PROTECT, related_name='weight_configs', to='registry.stampmetadata'),
        ),
    ]