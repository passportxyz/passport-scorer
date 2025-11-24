# Development Environment Setup Structure

## Modular Setup Scripts

Consolidated development setup into `dev-setup/` folder with modular scripts:

### setup.sh
Main orchestrator script that:
- Detects environment (container vs systemd)
- Runs full setup by calling other scripts
- Automatically adjusts PostgreSQL startup based on environment

### install.sh
Basic dependency installer:
- Python and Poetry
- PostgreSQL
- Rust and cargo tools
- Build tools

### create_test_data.py
Django ORM-based test data creation:
- Creates test communities (IDs 1-3)
- Creates scorers with weights
- Creates API keys for testing

### start-postgres.sh
PostgreSQL restart helper for containers

## Database Configuration

- **Database**: passport_scorer_dev
- **User**: passport_scorer
- **Password**: devpassword123

## SQLX Development Database Setup

SQLX requires a PostgreSQL database at compile time for query validation. The setup process:

1. Creates PostgreSQL database `passport_scorer_dev`
2. Runs Django migrations to create schema
3. Manually creates any missing tables that Django migrations didn't create
4. Installs sqlx-cli: `cargo install sqlx-cli --no-default-features --features postgres,rustls`
5. Sets DATABASE_URL environment variable for SQLX compilation
6. Can generate offline data with `cargo sqlx prepare` for CI/CD without database

## Common Issues

- **Missing tables**: Django migrations may show as applied but tables don't exist - use `migrate --run-syncdb`
- **Type mismatches**: Some tables use BIGINT (i64) not INT (i32) for IDs
- **Missing columns**: May need to manually ALTER TABLE to add columns Django expects

See: `dev-setup/setup.sh`, `dev-setup/install.sh`, `dev-setup/create_test_data.py`, `rust-scorer/Cargo.toml`
