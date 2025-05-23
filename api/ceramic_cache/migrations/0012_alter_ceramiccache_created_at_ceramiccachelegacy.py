# Generated by Django 4.2.3 on 2023-07-26 17:16

from django.db import migrations, models

import account.models


class Migration(migrations.Migration):
    dependencies = [
        ("ceramic_cache", "0011_alter_ceramiccache_created_at"),
    ]

    operations = [
        migrations.AlterField(
            model_name="ceramiccache",
            name="created_at",
            field=models.DateTimeField(
                auto_now_add=True,
                help_text="This is the timestamp that this DB record was created (it is not necesarily the stamp issuance timestamp)",
                null=True,
            ),
        ),
        migrations.CreateModel(
            name="CeramicCacheLegacy",
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
                    "address",
                    account.models.EthAddressField(
                        db_index=True, max_length=100, null=True
                    ),
                ),
                (
                    "provider",
                    models.CharField(db_index=True, default="", max_length=256),
                ),
                ("stamp", models.JSONField(default=dict)),
            ],
            options={
                "unique_together": {("address", "provider")},
            },
        ),
    ]
