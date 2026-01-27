# Generated manually
# - EmbedStampSection: customization FK → community FK, drop unique_together
# - EmbedStampSectionItem: platform_id CharField → platform FK to PlatformMetadata

import django.db.models.deletion
from django.db import migrations, models


def migrate_section_customization_to_community(apps, schema_editor):
    """
    For every EmbedStampSection, set community_id from the
    linked customization's scorer_id (which IS the community id).
    """
    EmbedStampSection = apps.get_model("account", "EmbedStampSection")
    Customization = apps.get_model("account", "Customization")

    for section in EmbedStampSection.objects.all():
        customization = Customization.objects.get(pk=section.customization_id)
        section.community_id = customization.scorer_id
        section.save(update_fields=["community_id"])


def migrate_platform_id_to_fk(apps, schema_editor):
    """
    For every EmbedStampSectionItem, ensure a matching
    PlatformMetadata row exists and point the new FK at it.
    """
    PlatformMetadata = apps.get_model("registry", "PlatformMetadata")
    EmbedStampSectionItem = apps.get_model("account", "EmbedStampSectionItem")

    for item in EmbedStampSectionItem.objects.all():
        platform, _ = PlatformMetadata.objects.get_or_create(
            platform_id=item.old_platform_id,
            defaults={"name": item.old_platform_id},
        )
        item.platform_id = platform.pk
        item.save(update_fields=["platform_id"])


class Migration(migrations.Migration):

    dependencies = [
        ("account", "0050_merge_20260126_2007"),
        ("registry", "0060_platformmetadata"),
    ]

    operations = [
        # ===== EmbedStampSection: customization → community =====

        # 1. Drop old unique_together that references customization
        migrations.AlterUniqueTogether(
            name="embedstampsection",
            unique_together=set(),
        ),
        # 2. Add nullable community FK
        migrations.AddField(
            model_name="embedstampsection",
            name="community",
            field=models.ForeignKey(
                help_text="The community this section belongs to",
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="embed_stamp_sections",
                to="account.community",
            ),
        ),
        # 3. Data migration: populate community from customization.scorer_id
        migrations.RunPython(
            migrate_section_customization_to_community,
            migrations.RunPython.noop,
        ),
        # 4. Remove old customization FK
        migrations.RemoveField(
            model_name="embedstampsection",
            name="customization",
        ),
        # 5. Make community FK non-nullable
        migrations.AlterField(
            model_name="embedstampsection",
            name="community",
            field=models.ForeignKey(
                help_text="The community this section belongs to",
                on_delete=django.db.models.deletion.CASCADE,
                related_name="embed_stamp_sections",
                to="account.community",
            ),
        ),

        # ===== EmbedStampSectionItem: platform_id CharField → platform FK =====

        # 6. Drop old unique_together that references platform_id
        migrations.AlterUniqueTogether(
            name="embedstampsectionitem",
            unique_together=set(),
        ),
        # 7. Rename old CharField so we can reuse the DB column
        migrations.RenameField(
            model_name="embedstampsectionitem",
            old_name="platform_id",
            new_name="old_platform_id",
        ),
        # 8. Add nullable FK field
        migrations.AddField(
            model_name="embedstampsectionitem",
            name="platform",
            field=models.ForeignKey(
                help_text="Select the platform/stamp to include in this section",
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="embed_section_items",
                to="registry.platformmetadata",
            ),
        ),
        # 9. Data migration: populate FK from old CharField values
        migrations.RunPython(migrate_platform_id_to_fk, migrations.RunPython.noop),
        # 10. Remove old CharField
        migrations.RemoveField(
            model_name="embedstampsectionitem",
            name="old_platform_id",
        ),
        # 11. Make FK non-nullable
        migrations.AlterField(
            model_name="embedstampsectionitem",
            name="platform",
            field=models.ForeignKey(
                help_text="Select the platform/stamp to include in this section",
                on_delete=django.db.models.deletion.CASCADE,
                related_name="embed_section_items",
                to="registry.platformmetadata",
            ),
        ),
        # 12. Re-add unique_together with new FK field
        migrations.AlterUniqueTogether(
            name="embedstampsectionitem",
            unique_together={("section", "platform")},
        ),
    ]
