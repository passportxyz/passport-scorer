# Generated manually to optimize get_passport_stamps query performance

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("ceramic_cache", "0032_alter_ban_type_alter_ceramiccache_source_scorer_id"),
    ]

    operations = [
        migrations.RunSQL(
            "CREATE INDEX IF NOT EXISTS ceramic_cache_ceramiccache_address_deleted_at_id_desc ON ceramic_cache_ceramiccache (address, deleted_at, id DESC);",
            reverse_sql="DROP INDEX IF EXISTS ceramic_cache_ceramiccache_address_deleted_at_id_desc;"
        ),
    ]