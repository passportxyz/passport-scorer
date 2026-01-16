from django.db import migrations


class Migration(migrations.Migration):
    """
    Add a partial index optimized for the common query pattern:
    WHERE address = X AND deleted_at IS NULL ORDER BY id DESC

    The existing index (address, deleted_at, id DESC) doesn't work well with IS NULL.
    This partial index is specifically optimized for non-deleted stamp lookups.
    """

    atomic = False  # Required for CONCURRENTLY

    dependencies = [
        ("ceramic_cache", "0033_add_composite_index_address_deleted_at_id"),
    ]

    operations = [
        migrations.RunSQL(
            sql="CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_cc_addr_id_not_deleted ON ceramic_cache_ceramiccache (address, id DESC) WHERE deleted_at IS NULL;",
            reverse_sql="DROP INDEX CONCURRENTLY IF EXISTS idx_cc_addr_id_not_deleted;",
        ),
    ]
