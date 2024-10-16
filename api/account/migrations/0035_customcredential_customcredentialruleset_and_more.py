# Generated by Django 4.2.6 on 2024-09-11 22:11

import django.db.models.deletion
from django.db import migrations, models

import account.models


class Migration(migrations.Migration):
    dependencies = [
        ("account", "0034_customgithubstamp"),
    ]

    operations = [
        migrations.CreateModel(
            name="CustomCredential",
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
                    "weight",
                    models.DecimalField(decimal_places=4, default=0.0, max_digits=7),
                ),
                ("display_name", models.CharField(max_length=64)),
                (
                    "description",
                    models.CharField(blank=True, max_length=256, null=True),
                ),
                (
                    "customization",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="custom_credentials",
                        to="account.customization",
                    ),
                ),
            ],
        ),
        migrations.CreateModel(
            name="CustomCredentialRuleset",
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
                    "credential_type",
                    models.CharField(
                        choices=[("DEVEL", "Developer List")], max_length=5
                    ),
                ),
                (
                    "definition",
                    models.JSONField(
                        validators=[
                            account.models.validate_custom_stamp_ruleset_definition
                        ]
                    ),
                ),
                ("name", models.CharField(max_length=64)),
                ("provider_id", models.CharField(max_length=256, unique=True)),
            ],
        ),
        migrations.CreateModel(
            name="CustomPlatform",
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
                    "platform_type",
                    models.CharField(
                        choices=[("DEVEL", "Developer List")], max_length=5
                    ),
                ),
                (
                    "name",
                    models.CharField(
                        help_text="Internal name", max_length=64, unique=True
                    ),
                ),
                (
                    "display_name",
                    models.CharField(
                        blank=True,
                        help_text="This and all remaining fields are optional, there are defaults defined for each platform type",
                        max_length=64,
                        null=True,
                    ),
                ),
                (
                    "icon_url",
                    models.CharField(
                        blank=True,
                        help_text="e.g. ./assets/icon.svg",
                        max_length=64,
                        null=True,
                    ),
                ),
                (
                    "description",
                    models.CharField(blank=True, max_length=256, null=True),
                ),
                (
                    "banner_heading",
                    models.CharField(blank=True, max_length=64, null=True),
                ),
                (
                    "banner_content",
                    models.CharField(blank=True, max_length=256, null=True),
                ),
                (
                    "banner_cta_text",
                    models.CharField(
                        blank=True,
                        help_text="If either CTA field is set, both must be set",
                        max_length=256,
                        null=True,
                    ),
                ),
                (
                    "banner_cta_url",
                    models.CharField(blank=True, max_length=256, null=True),
                ),
            ],
        ),
        migrations.AlterField(
            model_name="includedchainid",
            name="chain_id",
            field=models.CharField(
                help_text="Chain ID in hex format (0x1)! You can find this on for example on: https://chainlist.org",
                max_length=200,
                validators=[account.models.hex_number_validator],
            ),
        ),
        migrations.DeleteModel(
            name="CustomGithubStamp",
        ),
        migrations.AddField(
            model_name="customcredential",
            name="platform",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT, to="account.customplatform"
            ),
        ),
        migrations.AddField(
            model_name="customcredential",
            name="ruleset",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                to="account.customcredentialruleset",
            ),
        ),
    ]
