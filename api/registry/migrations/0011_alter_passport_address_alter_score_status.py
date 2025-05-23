# Generated by Django 4.2.2 on 2023-06-28 18:52

from django.db import migrations, models

import account.models


class Migration(migrations.Migration):
    dependencies = [
        ("registry", "0010_passport_requires_calculation"),
    ]

    operations = [
        migrations.AlterField(
            model_name="passport",
            name="address",
            field=account.models.EthAddressField(
                db_index=True, max_length=100, null=True
            ),
        ),
        migrations.AlterField(
            model_name="score",
            name="status",
            field=models.CharField(
                choices=[
                    ("PROCESSING", "PROCESSING"),
                    ("DONE", "DONE"),
                    ("ERROR", "ERROR"),
                ],
                db_index=True,
                default=None,
                max_length=20,
                null=True,
            ),
        ),
    ]
