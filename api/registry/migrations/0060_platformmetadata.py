# Generated manually for PlatformMetadata model

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("registry", "0059_add_stamp_metadata"),
    ]

    operations = [
        migrations.CreateModel(
            name="PlatformMetadata",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "platform_id",
                    models.CharField(
                        db_index=True,
                        help_text="The platform ID from stampMetadata.json (e.g. 'Discord', 'Github')",
                        max_length=100,
                        unique=True,
                    ),
                ),
                (
                    "name",
                    models.CharField(
                        help_text="Display name of the platform (e.g. 'Discord', 'GitHub')",
                        max_length=255,
                    ),
                ),
            ],
            options={
                "verbose_name": "Platform Metadata",
                "verbose_name_plural": "Platform Metadata",
                "ordering": ["name"],
            },
        ),
        migrations.AddField(
            model_name="stampmetadata",
            name="platform",
            field=models.ForeignKey(
                blank=True,
                help_text="The platform this stamp provider belongs to",
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="stamps",
                to="registry.platformmetadata",
            ),
        ),
    ]
