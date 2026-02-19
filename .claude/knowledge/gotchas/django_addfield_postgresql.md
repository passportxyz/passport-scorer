# Django BooleanField AddField PostgreSQL Behavior

## [2026-02-10] PostgreSQL 11+ safe migration behavior

Django `AddField` with `BooleanField(default=False)` generates:
```sql
ALTER TABLE ADD COLUMN field BOOLEAN DEFAULT false NOT NULL;
ALTER TABLE ALTER COLUMN field DROP DEFAULT;
```

On PostgreSQL 11+, `ADD COLUMN` with a non-volatile DEFAULT does NOT cause a table rewrite. The default is stored in `pg_attribute.attmissingval` catalog. Django immediately drops the DEFAULT in the same transaction, but both operations are fast (metadata-only).

**Result**: Effectively zero-downtime safe for non-volatile defaults like `BooleanField(default=False)` on PostgreSQL 11+.

**Warning**: For PostgreSQL < 11, this WOULD cause a full table rewrite and lock.

See: `api/account/models.py`
