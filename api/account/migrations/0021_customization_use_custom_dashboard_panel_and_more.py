# Generated by Django 4.2.6 on 2024-03-27 12:05

import re

import django.core.validators
from django.db import migrations, models

import account.models


class Migration(migrations.Migration):
    dependencies = [
        ("account", "0020_alter_nonce_nonce_customization"),
    ]

    operations = [
        migrations.AddField(
            model_name="customization",
            name="use_custom_dashboard_panel",
            field=models.BooleanField(default=False),
        ),
        migrations.AlterField(
            model_name="customization",
            name="customization_background_1",
            field=account.models.RGBAHexColorField(
                blank=True,
                help_text="Background color 1. RGBA hex value expected, for example `#aaff6655`",
                max_length=9,
                null=True,
                validators=[
                    django.core.validators.RegexValidator(
                        re.compile("^#[A-Fa-f0-9]{8}$"),
                        "Enter a valid RGBA color as hex string ",
                        "invalid",
                    )
                ],
            ),
        ),
        migrations.AlterField(
            model_name="customization",
            name="customization_background_2",
            field=account.models.RGBAHexColorField(
                blank=True,
                help_text="Background color 2. RGBA hex value expected, for example `#aaff6655`",
                max_length=9,
                null=True,
                validators=[
                    django.core.validators.RegexValidator(
                        re.compile("^#[A-Fa-f0-9]{8}$"),
                        "Enter a valid RGBA color as hex string ",
                        "invalid",
                    )
                ],
            ),
        ),
        migrations.AlterField(
            model_name="customization",
            name="customization_foreground_1",
            field=account.models.RGBAHexColorField(
                blank=True,
                help_text="Foreground color. RGBA hex value expected, for example `#aaff6655`",
                max_length=9,
                null=True,
                validators=[
                    django.core.validators.RegexValidator(
                        re.compile("^#[A-Fa-f0-9]{8}$"),
                        "Enter a valid RGBA color as hex string ",
                        "invalid",
                    )
                ],
            ),
        ),
    ]
