# Generated manually
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("account", "0047_populate_topnav_dashboards"),
    ]

    operations = [
        migrations.CreateModel(
            name="EmbedStampSection",
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
                    "title",
                    models.CharField(
                        help_text="Title of the stamp section (e.g., 'Physical Verification', 'Web2 Platforms')",
                        max_length=255,
                    ),
                ),
                (
                    "order",
                    models.IntegerField(
                        default=0,
                        help_text="Display order of this section (lower numbers appear first)",
                    ),
                ),
                (
                    "created_at",
                    models.DateTimeField(auto_now_add=True),
                ),
                (
                    "updated_at",
                    models.DateTimeField(auto_now=True),
                ),
                (
                    "customization",
                    models.ForeignKey(
                        help_text="The customization configuration this section belongs to",
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="embed_stamp_sections",
                        to="account.customization",
                    ),
                ),
            ],
            options={
                "ordering": ["order", "id"],
            },
        ),
        migrations.CreateModel(
            name="EmbedStampSectionItem",
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
                    "platform_id",
                    models.CharField(
                        max_length=100,
                        choices=[
                            ("Binance", "Binance - Binance Account Bound Token (BABT)"),
                            ("Biometrics", "Biometrics - 3D facial liveness detection"),
                            ("Coinbase", "Coinbase - Coinbase verification"),
                            (
                                "HumanIdKyc",
                                "Government ID - Government-issued ID verification",
                            ),
                            (
                                "CleanHands",
                                "Proof of Clean Hands - ID + liveness + sanctions check",
                            ),
                            (
                                "HumanIdPhone",
                                "Phone Verification - Phone number verification",
                            ),
                            ("Discord", "Discord - Discord account ownership"),
                            ("Github", "GitHub - GitHub commit activity"),
                            ("Google", "Google - Google account ownership"),
                            ("Linkedin", "LinkedIn - LinkedIn account ownership"),
                        ],
                        help_text="Select the platform/stamp to include in this section",
                    ),
                ),
                (
                    "order",
                    models.IntegerField(
                        default=0,
                        help_text="Display order within the section (lower numbers appear first)",
                    ),
                ),
                (
                    "created_at",
                    models.DateTimeField(auto_now_add=True),
                ),
                (
                    "updated_at",
                    models.DateTimeField(auto_now=True),
                ),
                (
                    "section",
                    models.ForeignKey(
                        help_text="The section this stamp belongs to",
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="items",
                        to="account.embedstampsection",
                    ),
                ),
            ],
            options={
                "ordering": ["order", "id"],
            },
        ),
        migrations.AlterUniqueTogether(
            name="embedstampsection",
            unique_together={("customization", "order")},
        ),
        migrations.AlterUniqueTogether(
            name="embedstampsectionitem",
            unique_together={("section", "platform_id")},
        ),
    ]

