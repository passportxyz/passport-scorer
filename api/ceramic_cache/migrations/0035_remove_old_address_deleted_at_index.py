from django.db import migrations


class Migration(migrations.Migration):
    """
    Remove the old composite index now that the partial index is in place.

    The old index (address, deleted_at, id DESC) is suboptimal for IS NULL queries.
    The new partial index from 0034 handles these queries more efficiently.

    This is separated into its own migration so we can verify the new index
    works before removing the old one.
    """

    atomic = False  # Required for CONCURRENTLY

    dependencies = [
        ("ceramic_cache", "0034_optimize_address_lookup_partial_index"),
    ]

    operations = [
        migrations.RunSQL(
            sql="DROP INDEX CONCURRENTLY IF EXISTS ceramic_cache_ceramiccache_address_deleted_at_id_desc;",
            reverse_sql="CREATE INDEX CONCURRENTLY ceramic_cache_ceramiccache_address_deleted_at_id_desc ON ceramic_cache_ceramiccache (address, deleted_at, id DESC);",
        ),
    ]
