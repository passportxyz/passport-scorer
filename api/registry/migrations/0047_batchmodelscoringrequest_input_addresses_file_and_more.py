# Generated by Django 4.2.6 on 2025-06-06 05:55

import django.db.models.deletion
from django.db import migrations, models

import account.models
import registry.models


class Migration(migrations.Migration):
    dependencies = [
        ("registry", "0046_remove_batchmodelscoringrequest_s3_file_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="batchmodelscoringrequest",
            name="input_addresses_file",
            field=models.FileField(
                blank=True,
                null=True,
                upload_to=registry.models.input_addresses_file_upload_to,
            ),
        ),
        migrations.AddField(
            model_name="batchmodelscoringrequest",
            name="last_progress_update",
            field=models.DateTimeField(
                blank=True, help_text="Timestamp of last progress update", null=True
            ),
        ),
        migrations.AddField(
            model_name="batchmodelscoringrequest",
            name="results_file",
            field=models.FileField(
                blank=True,
                help_text="Will contain the exported data",
                null=True,
                upload_to=registry.models.results_file_upload_to,
            ),
        ),
        migrations.AddField(
            model_name="batchmodelscoringrequest",
            name="trigger_processing_file",
            field=models.FileField(
                blank=True,
                help_text="Just a file that is created automatically to trigger the processing. An EventBridge rule will be watching for files created in this folder.",
                null=True,
                upload_to=registry.models.trigger_processing_file_upload_to,
            ),
        ),
        migrations.AlterField(
            model_name="batchmodelscoringrequest",
            name="s3_filename",
            field=models.CharField(
                db_index=True,
                help_text="This is deprecated, in favour of `input_addresses_file`",
                max_length=100,
            ),
        ),
        migrations.AlterField(
            model_name="batchmodelscoringrequest",
            name="status",
            field=models.CharField(
                choices=[
                    ("PENDING", registry.models.BatchRequestStatus["PENDING"]),
                    ("DONE", registry.models.BatchRequestStatus["DONE"]),
                    ("ERROR", registry.models.BatchRequestStatus["ERROR"]),
                ],
                default=registry.models.BatchRequestStatus["PENDING"],
                max_length=20,
            ),
        ),
        migrations.CreateModel(
            name="BatchModelScoringRequestItem",
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
                    "status",
                    models.CharField(
                        choices=[
                            (
                                "PENDING",
                                registry.models.BatchRequestItemStatus["PENDING"],
                            ),
                            ("DONE", registry.models.BatchRequestItemStatus["DONE"]),
                            ("ERROR", registry.models.BatchRequestItemStatus["ERROR"]),
                        ],
                        default=registry.models.BatchRequestItemStatus["PENDING"],
                        max_length=20,
                    ),
                ),
                (
                    "address",
                    account.models.EthAddressField(db_index=True, max_length=42),
                ),
                ("result", models.JSONField(blank=True, default=None, null=True)),
                (
                    "batch_scoring_request",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="items",
                        to="registry.batchmodelscoringrequest",
                    ),
                ),
            ],
            options={
                "unique_together": {("batch_scoring_request", "address")},
            },
        ),
    ]
