"""
Replace EmbedStampSection + EmbedStampSectionItem with:
- EmbedSectionHeader (global section names)
- EmbedSectionOrder (per-customization section ordering)
- EmbedStampPlatform (per-customization platform assignments)

No data migration needed — still in development, no production data.
"""

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("account", "0051_embedstampsectionitem_platform_fk"),
        ("registry", "0060_platformmetadata"),
    ]

    operations = [
        # 1. Create EmbedSectionHeader
        migrations.CreateModel(
            name="EmbedSectionHeader",
            fields=[
                (
                    "id",
                    models.AutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("name", models.CharField(max_length=255, unique=True)),
            ],
            options={
                "ordering": ["name"],
            },
        ),
        # 2. Create EmbedSectionOrder
        migrations.CreateModel(
            name="EmbedSectionOrder",
            fields=[
                (
                    "id",
                    models.AutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("order", models.IntegerField(default=0)),
                (
                    "customization",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="embed_section_orders",
                        to="account.customization",
                    ),
                ),
                (
                    "section",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        to="account.embedsectionheader",
                    ),
                ),
            ],
            options={
                "ordering": ["order"],
                "unique_together": {("customization", "section")},
            },
        ),
        # 3. Create EmbedStampPlatform
        migrations.CreateModel(
            name="EmbedStampPlatform",
            fields=[
                (
                    "id",
                    models.AutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("order", models.IntegerField(default=0)),
                (
                    "customization",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="embed_stamp_platforms",
                        to="account.customization",
                    ),
                ),
                (
                    "section",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        to="account.embedsectionheader",
                    ),
                ),
                (
                    "platform",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        to="registry.platformmetadata",
                    ),
                ),
            ],
            options={
                "ordering": ["section__id", "order", "id"],
                "unique_together": {("customization", "platform")},
            },
        ),
        # 4. Remove old models
        migrations.DeleteModel(
            name="EmbedStampSectionItem",
        ),
        migrations.DeleteModel(
            name="EmbedStampSection",
        ),
    ]
