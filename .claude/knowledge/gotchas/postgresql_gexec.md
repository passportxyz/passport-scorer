# PostgreSQL gexec Database Creation

## [2025-11-24] PostgreSQL gexec Database Creation Fix

The original setup script used `\gexec` with a SELECT statement to conditionally create the database, but this approach had issues:

1. The script had `\\gexec` (double backslash) which was incorrect syntax
2. Even with correct `\gexec`, this approach can fail silently in some PostgreSQL configurations

### Solution

Split into two operations:

1. **Check if database exists**:
   ```bash
   psql -tc "SELECT 1 FROM pg_database WHERE datname = '${DB_NAME}'" | grep -q 1
   ```

2. **Create if it doesn't**:
   ```bash
   psql -c "CREATE DATABASE ${DB_NAME} OWNER ${DB_USER};"
   ```

This approach is more reliable and provides better error visibility.

See: `dev-setup/setup.sh`
