# Generated by Django 4.2.6 on 2024-03-07 22:58

from django.db import migrations, models

import account.models


class Migration(migrations.Migration):
    dependencies = [
        ("registry", "0030_alter_score_options"),
    ]

    operations = [
        migrations.CreateModel(
            name="StakeEvent",
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
                    "event_type",
                    models.CharField(
                        choices=[
                            ("SST", "Self Stake"),
                            ("CST", "Community Stake"),
                            ("SSW", "Self Stake Withdraw"),
                            ("CSW", "Community Stake Withdraw"),
                            ("SLA", "Slash"),
                            ("REL", "Release"),
                        ],
                        db_index=True,
                        max_length=3,
                    ),
                ),
                (
                    "chain",
                    models.SmallIntegerField(
                        choices=[("0", "Ethereum Mainnet"), ("1", "Optimism Mainnet")],
                        db_index=True,
                    ),
                ),
                (
                    "staker",
                    account.models.EthAddressField(db_index=True, max_length=42),
                ),
                (
                    "stakee",
                    account.models.EthAddressField(db_index=True, max_length=42),
                ),
                ("amount", models.DecimalField(decimal_places=0, max_digits=78)),
                ("block_number", models.DecimalField(decimal_places=0, max_digits=78)),
                ("tx_hash", models.CharField(max_length=66)),
                ("unlock_time", models.DateTimeField(blank=True, null=True)),
            ],
        ),
        migrations.CreateModel(
            name="Stake",
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
                    "chain",
                    models.SmallIntegerField(
                        choices=[("0", "Ethereum Mainnet"), ("1", "Optimism Mainnet")],
                        db_index=True,
                        default="0",
                    ),
                ),
                ("unlock_time", models.DateTimeField()),
                (
                    "last_updated_in_block",
                    models.DecimalField(db_index=True, decimal_places=0, max_digits=78),
                ),
                (
                    "staker",
                    account.models.EthAddressField(db_index=True, max_length=42),
                ),
                (
                    "stakee",
                    account.models.EthAddressField(db_index=True, max_length=42),
                ),
                (
                    "current_amount",
                    models.DecimalField(decimal_places=0, max_digits=78),
                ),
            ],
            options={
                "unique_together": {("staker", "stakee", "chain")},
            },
        ),
    ]
