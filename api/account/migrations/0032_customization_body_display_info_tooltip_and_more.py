# Generated by Django 4.2.6 on 2024-07-02 17:11

import re

import django.core.validators
from django.db import migrations, models

import account.models


class Migration(migrations.Migration):
    dependencies = [
        ("account", "0031_alter_allowlist_customization"),
    ]

    operations = [
        migrations.AddField(
            model_name="customization",
            name="body_display_info_tooltip",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="customization",
            name="body_info_tooltip_text",
            field=account.models.ReactNodeField(
                blank=True, help_text="The info tooltip text", null=True
            ),
        ),
        migrations.AddField(
            model_name="customization",
            name="button_action_type",
            field=models.CharField(
                choices=[
                    ("Simple Link", "Simple Link"),
                    ("Onchain Push", "Onchain Push"),
                ],
                default="Simple Link",
                max_length=25,
            ),
        ),
        migrations.AddField(
            model_name="customization",
            name="customization_background_3",
            field=account.models.RGBHexColorField(
                blank=True,
                help_text="Action button background color. RGB hex value expected, for example `#aaff66`",
                max_length=7,
                null=True,
                validators=[
                    django.core.validators.RegexValidator(
                        re.compile("^#[A-Fa-f0-9]{6}$"),
                        "Enter a valid RGBA color as hex string ",
                        "invalid",
                    )
                ],
            ),
        ),
        migrations.AddField(
            model_name="customization",
            name="customization_foreground_2",
            field=account.models.RGBHexColorField(
                blank=True,
                help_text="Action button text color. RGB hex value expected, for example `#aaff66`",
                max_length=7,
                null=True,
                validators=[
                    django.core.validators.RegexValidator(
                        re.compile("^#[A-Fa-f0-9]{6}$"),
                        "Enter a valid RGBA color as hex string ",
                        "invalid",
                    )
                ],
            ),
        ),
    ]
