# Development Environment Setup Guide

## Modular Setup Scripts

Development setup is consolidated in `dev-setup/` folder with modular scripts that handle environment detection and dependency installation.

### Setup Orchestration (setup.sh)

Main script that:
- Detects environment (container vs systemd)
- Runs full setup by calling other scripts
- Automatically adjusts PostgreSQL startup based on environment

### Dependency Installation (install.sh)

Basic dependency installer for:
- Python and Poetry
- PostgreSQL
- Rust and cargo tools
- Build tools

### Test Data Creation (create_test_data.py)

Django ORM-based test data creation:
- Creates test communities (IDs 1-3)
- Creates scorers with weights
- Creates API keys for testing

### Database Configuration

- **Database name**: passport_scorer_dev
- **Database user**: passport_scorer
- **Password**: devpassword123

## SQLX Development Database Setup

SQLX requires a PostgreSQL database at compile time for query validation.

### Setup Process

1. Create PostgreSQL database `passport_scorer_dev`
2. Run Django migrations to create schema: `poetry run python manage.py migrate --database=passport_scorer_dev`
3. Manually create any missing tables that Django migrations didn't create
4. Install sqlx-cli:
   ```bash
   cargo install sqlx-cli --no-default-features --features postgres,rustls
   ```
5. Set DATABASE_URL environment variable for SQLX compilation
6. Generate offline data with `cargo sqlx prepare` for CI/CD without database access

### Offline Query Support

For environments without database access (CI/CD), SQLX caches query metadata:
```bash
# Generate cached .sqlx/ directory
cargo sqlx prepare

# Build with cached data (no DB needed)
SQLX_OFFLINE=true cargo build
```

## Environment Detection

### The Problem

Development containers (Docker, dev containers) don't have systemd as PID 1, so PostgreSQL must be started differently than on regular systems.

### Detection Logic

The setup scripts check for:
- `/.dockerenv` or `/run/.containerenv` files
- systemd running with `pidof systemd`
- If any indicate container, uses direct postgres command instead of systemctl

### PostgreSQL Startup

**Container mode**:
```bash
sudo -u postgres /usr/bin/postgres -D /var/lib/postgresql/data &
```

**System mode**:
```bash
sudo systemctl start postgresql
```

### Container-Specific Requirements

Must create `/var/run/postgresql` directory for Unix socket in containers as it's not created automatically without systemd.

## Common Issues

### Missing Tables After Migration

Django migrations may show as applied but tables don't exist. Solution: Use `migrate --run-syncdb`

```bash
cd api
poetry run python manage.py migrate --database=passport_scorer_dev --run-syncdb
```

### Type Mismatches

Some tables use BIGINT (i64) not INT (i32) for IDs. Check database schema before writing queries.

### Missing Columns

May need to manually ALTER TABLE to add columns Django expects:

```sql
ALTER TABLE table_name ADD COLUMN column_name column_type;
```

## Ubuntu Container Setup

For containers without root access (e.g., Node.js base images running as 'node' user), see `dev-setup/install-ubuntu-container.sh`.

Uses micromamba for all dependencies including:
- python=3.12, postgresql=14, redis-server, gcc, g++, make, pkg-config, openssl, libpq

PostgreSQL runs in userspace at `~/pgdata` (no postgres system user needed).
Redis runs daemonized: `redis-server --daemonize yes --bind 127.0.0.1`

### Rust Compilation Environment Variables (Ubuntu Container)

```bash
CC=$CONDA_PREFIX/bin/gcc
AR=$CONDA_PREFIX/bin/ar
LIBRARY_PATH=$CONDA_PREFIX/lib
LD_LIBRARY_PATH=$CONDA_PREFIX/lib
C_INCLUDE_PATH=$CONDA_PREFIX/include
PKG_CONFIG_PATH=$CONDA_PREFIX/lib/pkgconfig
SQLX_OFFLINE=true
```

Activation helper: `source ~/activate-passport-dev.sh`

## References

- `/dev-setup/setup.sh` - Main orchestration script
- `/dev-setup/install.sh` - Dependency installation
- `/dev-setup/install-ubuntu-container.sh` - Container-specific setup
- `/dev-setup/create_test_data.py` - Test data creation
- `/dev-setup/start-postgres.sh` - PostgreSQL restart helper
