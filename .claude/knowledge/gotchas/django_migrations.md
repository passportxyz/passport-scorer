# Django Migrations Gotchas

## [2025-11-24] Django Migrations Out of Sync

When Django says "No migrations to apply" but tables don't exist, this usually means the migrations were marked as applied in Django's migration history table but the actual tables were never created. This can happen when:

1. Database was created after migrations were recorded
2. Database was dropped but migration history persisted
3. Multiple database configs got mixed up

### Solution

Use `migrate --run-syncdb` to force Django to create missing tables, or delete the django_migrations table and run migrations again.

See: `dev-setup/setup.sh`
