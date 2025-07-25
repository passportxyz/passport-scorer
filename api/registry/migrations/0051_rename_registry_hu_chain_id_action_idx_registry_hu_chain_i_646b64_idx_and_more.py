# Generated by Django 4.2.6 on 2025-06-30 13:34

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("registry", "0050_populate_human_points_config"),
    ]

    operations = [
        migrations.RenameIndex(
            model_name="humanpoints",
            new_name="registry_hu_chain_i_646b64_idx",
            old_name="registry_hu_chain_id_action_idx",
        ),
        migrations.AlterField(
            model_name="humanpoints",
            name="chain_id",
            field=models.IntegerField(
                blank=True,
                db_index=True,
                help_text="Chain ID for mint actions (PMT, HIM)",
                null=True,
            ),
        ),
    ]
