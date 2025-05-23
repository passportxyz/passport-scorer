# Generated by Django 4.1.5 on 2023-01-26 22:43

from django.db import migrations, models

import account.models


class Migration(migrations.Migration):
    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="CeramicCache",
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
                ("address", account.models.EthAddressField(max_length=100, null=True)),
                (
                    "provider",
                    models.CharField(db_index=True, default="", max_length=256),
                ),
                ("passport", models.JSONField(default=dict)),
            ],
            options={
                "unique_together": {("address", "provider")},
            },
        ),
    ]
