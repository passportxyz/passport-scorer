import django.db.models.deletion
from django.db import migrations, models

import account.models


class Migration(migrations.Migration):
    dependencies = [("registry", "0060_platformmetadata")]

    operations = [
        migrations.AddField(
            model_name="hashscorerlink",
            name="chain_id",
            field=models.PositiveBigIntegerField(default=1, db_default=1),
        ),
        migrations.CreateModel(
            name="ChainWalletScore",
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
                ("chain_id", models.PositiveBigIntegerField()),
                ("address", account.models.EthAddressField(max_length=42)),
                ("response", models.JSONField()),
                (
                    "community",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        to="account.community",
                    ),
                ),
            ],
            options={
                "constraints": [
                    models.UniqueConstraint(
                        fields=("community", "chain_id", "address"),
                        name="chain_wallet_score_identity",
                    ),
                    models.CheckConstraint(
                        condition=models.Q(
                            chain_id__gt=0, chain_id__lte=9007199254740991
                        ),
                        name="chain_wallet_score_chain",
                    ),
                ],
            },
        ),
    ]
