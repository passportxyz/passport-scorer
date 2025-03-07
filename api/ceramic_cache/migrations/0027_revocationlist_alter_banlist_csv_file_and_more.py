# Generated by Django 4.2.6 on 2024-12-03 04:47

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("ceramic_cache", "0026_banlist_ban_type_alter_ban_created_at_and_more"),
    ]

    operations = [
        migrations.CreateModel(
            name="RevocationList",
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
                    "name",
                    models.CharField(
                        blank=True, db_index=True, default="", max_length=256, null=True
                    ),
                ),
                ("description", models.TextField(blank=True, default="", null=True)),
                (
                    "csv_file",
                    models.FileField(max_length=1024, upload_to="revocation_list"),
                ),
            ],
        ),
        migrations.AlterField(
            model_name="banlist",
            name="csv_file",
            field=models.FileField(max_length=1024, upload_to="ban_list"),
        ),
        migrations.AddField(
            model_name="revocation",
            name="revocation_list",
            field=models.ForeignKey(
                blank=True,
                default=None,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="revocation_list",
                to="ceramic_cache.revocationlist",
            ),
        ),
    ]
