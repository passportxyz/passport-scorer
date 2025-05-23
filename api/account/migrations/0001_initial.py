# Generated by Django 4.1.4 on 2022-12-09 09:45

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        ("scorer_weighted", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="Account",
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
                ("address", models.CharField(max_length=100)),
                (
                    "user",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="account",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
        ),
        migrations.CreateModel(
            name="Community",
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
                ("name", models.CharField(max_length=100)),
                (
                    "description",
                    models.CharField(default="My community", max_length=100),
                ),
                (
                    "account",
                    models.ForeignKey(
                        default=None,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="community",
                        to="account.account",
                    ),
                ),
                (
                    "scorer",
                    models.ForeignKey(
                        default=None,
                        on_delete=django.db.models.deletion.PROTECT,
                        to="scorer_weighted.scorer",
                    ),
                ),
            ],
            options={
                "verbose_name_plural": "Communities",
            },
        ),
        migrations.CreateModel(
            name="AccountAPIKey",
            fields=[
                (
                    "id",
                    models.CharField(
                        editable=False,
                        max_length=150,
                        primary_key=True,
                        serialize=False,
                        unique=True,
                    ),
                ),
                ("prefix", models.CharField(editable=False, max_length=8, unique=True)),
                ("hashed_key", models.CharField(editable=False, max_length=150)),
                ("created", models.DateTimeField(auto_now_add=True, db_index=True)),
                (
                    "name",
                    models.CharField(
                        default=None,
                        help_text="A free-form name for the API key. Need not be unique. 50 characters max.",
                        max_length=50,
                    ),
                ),
                (
                    "revoked",
                    models.BooleanField(
                        blank=True,
                        default=False,
                        help_text="If the API key is revoked, clients cannot use it anymore. (This cannot be undone.)",
                    ),
                ),
                (
                    "expiry_date",
                    models.DateTimeField(
                        blank=True,
                        help_text="Once API key expires, clients cannot use it anymore.",
                        null=True,
                        verbose_name="Expires",
                    ),
                ),
                (
                    "account",
                    models.ForeignKey(
                        default=None,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="api_key",
                        to="account.account",
                    ),
                ),
            ],
            options={
                "verbose_name": "API key",
                "verbose_name_plural": "API keys",
                "ordering": ("-created",),
                "abstract": False,
            },
        ),
    ]
