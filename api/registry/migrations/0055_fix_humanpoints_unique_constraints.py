# Generated manually to fix unique constraints for HumanPoints model with correct action codes

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("registry", "0054_remove_humanpointsconfig_effective_date"),
    ]

    operations = [
        # First drop the old constraints if they exist
        migrations.RunSQL(
            "DROP INDEX IF EXISTS idx_binary_actions;",
            reverse_sql="",
        ),
        migrations.RunSQL(
            "DROP INDEX IF EXISTS idx_mint_actions;",
            reverse_sql="",
        ),
        # Unique constraint for binary actions (stamps, staking) using 3-letter codes
        migrations.RunSQL(
            "CREATE UNIQUE INDEX idx_binary_actions ON registry_humanpoints(address, action) "
            "WHERE action IN ('HKY', 'ISB', 'ISS', 'ISG', 'CSB', 'CSE', 'CST', 'SCB');",
            reverse_sql="DROP INDEX IF EXISTS idx_binary_actions;"
        ),
        # Unique constraint for mint actions (with tx_hash) using 3-letter codes
        migrations.RunSQL(
            "CREATE UNIQUE INDEX idx_mint_actions ON registry_humanpoints(address, action, tx_hash) "
            "WHERE action IN ('PMT', 'HIM');",
            reverse_sql="DROP INDEX IF EXISTS idx_mint_actions;"
        ),
        # Unique constraint for human keys (using nullifier stored in tx_hash field)
        migrations.RunSQL(
            "CREATE UNIQUE INDEX idx_human_keys ON registry_humanpoints(address, action, tx_hash) "
            "WHERE action = 'HKY';",
            reverse_sql="DROP INDEX IF EXISTS idx_human_keys;"
        ),
    ]