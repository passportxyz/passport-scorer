# Generated by Django 4.2.3 on 2023-07-24 11:02

from django.db import migrations, models

import account.models


class Migration(migrations.Migration):
    dependencies = [
        ("cgrants", "0004_contribution_amount_per_period_usdt"),
    ]

    operations = [
        migrations.CreateModel(
            name="ProtocolContributions",
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
                    "ext_id",
                    models.CharField(
                        db_index=True, default="", max_length=66, unique=True
                    ),
                ),
                (
                    "contributor",
                    account.models.EthAddressField(
                        db_index=True, default="", max_length=100
                    ),
                ),
                (
                    "round",
                    account.models.EthAddressField(
                        db_index=True, default="", max_length=100
                    ),
                ),
                (
                    "project",
                    account.models.EthAddressField(
                        db_index=True, default="", max_length=100
                    ),
                ),
                (
                    "amount",
                    models.DecimalField(
                        db_index=True,
                        decimal_places=18,
                        default=0,
                        help_text="The USD amount contributed",
                        max_digits=64,
                    ),
                ),
                (
                    "data",
                    models.JSONField(
                        default=dict,
                        help_text="Original contribution data in JSON format",
                    ),
                ),
            ],
        ),
        migrations.AlterField(
            model_name="grantcontributionindex",
            name="amount",
            field=models.DecimalField(
                db_index=True,
                decimal_places=18,
                default=0,
                help_text="The USD amount contributed",
                max_digits=64,
            ),
        ),
    ]
