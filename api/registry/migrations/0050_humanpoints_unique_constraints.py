# Generated manually to add unique constraints for HumanPoints model

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("registry", "0049_humanpointprogramstats_humanpointsmultiplier_and_more"),
    ]

    operations = [
        # Unique constraint for binary actions (stamps, staking)
        migrations.RunSQL(
            "CREATE UNIQUE INDEX idx_binary_actions ON registry_humanpoints(address, action) "
            "WHERE action IN ('human_keys', 'identity_staking_bronze', 'identity_staking_silver', "
            "'identity_staking_gold', 'community_staking_beginner', 'community_staking_experienced', "
            "'community_staking_trusted', 'scoring_bonus');",
            reverse_sql="DROP INDEX IF EXISTS idx_binary_actions;"
        ),
        # Unique constraint for mint actions (with tx_hash)
        migrations.RunSQL(
            "CREATE UNIQUE INDEX idx_mint_actions ON registry_humanpoints(address, action, tx_hash) "
            "WHERE action IN ('passport_mint', 'holonym_mint');",
            reverse_sql="DROP INDEX IF EXISTS idx_mint_actions;"
        ),
    ]