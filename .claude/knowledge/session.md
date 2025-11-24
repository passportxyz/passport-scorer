### [15:40] [gotchas] ALB Listener Rule Priority Conflicts - Third Shift
**Details**: When refactoring infrastructure to use routing-rules.ts, old listener rules persist in AWS even after code is removed. This causes "PriorityInUse" errors when trying to create new rules with the same priorities.

**Solution History**:
1. First shift: V2 API (2021→2110, 2023→2112), Ceramic Cache (1000-1010 → 1011-1020), Embed (2100-2103 → 2104-2106)
2. But old rules still existed at: 1001, 1002, 1003, 1004, 1006, 1007, 1010, 1012, 1015, 2021, 2023, 2100, 2101, 2103
3. Second shift (2025-11-24): Ceramic Cache range shifted again (1011-1020 → 1030-1039) to skip ALL old rules

**Current Priority Assignments**:
- V2 API: 2110 (models-score), 2112 (stamps-score)
- Ceramic Cache: 1030-1039 (submit, score, stamps bulk, weights, etc.)
- Embed (internal ALB): 2104-2106
- App API: 3000-3001

**Old priorities to avoid**: 1001-1020, 2021, 2023, 2100-2103

**Long-term fix**: Delete old AWS listener rules manually or via AWS CLI when safe to do so.
**Files**: infra/lib/scorer/routing-rules.ts
---

### [17:30] [gotcha] Django migrations out of sync
**Details**: When Django says "No migrations to apply" but tables don't exist, this usually means the migrations were marked as applied in Django's migration history table but the actual tables were never created. This can happen when:
1. Database was created after migrations were recorded
2. Database was dropped but migration history persisted
3. Multiple database configs got mixed up

Solution: Use `migrate --run-syncdb` to force Django to create missing tables, or delete the django_migrations table and run migrations again.
**Files**: dev-setup/setup.sh
---

### [17:34] [gotcha] PostgreSQL gexec database creation fix
**Details**: The original setup script used `\gexec` with a SELECT statement to conditionally create the database, but this approach had issues:
1. The script had `\\gexec` (double backslash) which was incorrect syntax
2. Even with correct `\gexec`, this approach can fail silently in some PostgreSQL configurations

Fixed by splitting into two operations:
1. Check if database exists: `psql -tc "SELECT 1 FROM pg_database WHERE datname = '${DB_NAME}'" | grep -q 1`
2. Create if it doesn't: `psql -c "CREATE DATABASE ${DB_NAME} OWNER ${DB_USER};"`

This approach is more reliable and provides better error visibility.
**Files**: dev-setup/setup.sh
---

### [17:37] [gotcha] WeightConfiguration CSV optional field handling
**Details**: The WeightConfiguration model has an optional csv_source FileField. The admin's save_model() method was causing a ValueError "The 'csv_source' attribute has no file associated with it" when saving without a CSV file.

Fixed by:
1. In save_model(): Check if obj.csv_source exists AND has a 'file' attribute before processing CSV
2. In clean_csv_source(): Return early if no csv_source is provided (it's optional)

This allows WeightConfiguration to be created either:
- With a CSV file that auto-populates WeightConfigurationItems
- Without a CSV file, using inline forms to manually add WeightConfigurationItems
**Files**: api/registry/admin.py
---

### [17:49] [api] CORS Support for Ceramic Cache Endpoints
**Details**: Added CORS support to Rust scorer to fix browser access issues for ceramic cache endpoints.

Configuration matches Python's permissive CORS settings:
- CORS_ALLOW_ALL_ORIGINS = True (allows any origin)
- Allows all methods (GET, POST, PATCH, DELETE, OPTIONS, etc.)
- Allows all headers

Implementation:
1. Added "cors" feature to tower-http dependency in Cargo.toml
2. Added CorsLayer to the Axum app with tower_http::cors::Any for all settings
3. Layer added before TraceLayer in the middleware stack

This fixes CORS errors when ceramic cache endpoints are called from:
- https://app.passport.xyz
- https://app.review.passport.xyz
- https://app.staging.passport.xyz
- localhost
- Any other origin (matches Python's allow-all approach)
**Files**: rust-scorer/Cargo.toml, rust-scorer/src/api/server.rs, api/scorer/settings/base.py
---

