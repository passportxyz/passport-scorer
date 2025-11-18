# Development Environment Setup Guide

This guide provides instructions for setting up a complete development environment for the Passport Scorer project, including PostgreSQL database setup for both Django (Python) and SQLX (Rust) development.

## Overview

The Passport Scorer consists of:
- **Django API** (Python) - The existing scoring API
- **Rust Scorer** - High-performance Rust implementation with SQLX for compile-time SQL validation
- **PostgreSQL Database** - Shared database used by both implementations

## Prerequisites

- Linux-based system (tested on Fedora/RHEL)
- `sudo` access for package installation
- At least 4GB of RAM
- 10GB of free disk space

## Quick Start

For a complete automated setup, run:

```bash
# Clone the repository
git clone <repository-url>
cd passport-scorer

# Run the automated setup script
./setup-dev-container.sh
```

This script will:
1. Install all required dependencies (PostgreSQL, Python, Poetry, Rust)
2. Setup and configure PostgreSQL
3. Create the development database
4. Run Django migrations
5. Create test data
6. Configure environment for SQLX

## Manual Setup Instructions

### 1. Install Basic Dependencies

```bash
# Install Python 3.12
sudo dnf install -y python3.12 python3.12-devel

# Install Poetry (Python package manager)
curl -sSL https://install.python-poetry.org | python3.12 -
export PATH="$HOME/.local/bin:$PATH"

# Install Rust
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y
source "$HOME/.cargo/env"

# Install build dependencies
sudo dnf install -y gcc openssl-devel pkg-config git curl
```

### 2. Setup PostgreSQL

```bash
# Install PostgreSQL
sudo dnf install -y postgresql postgresql-server postgresql-contrib

# For container environments (without systemd):
sudo -u postgres /usr/bin/initdb -D /var/lib/postgresql/data
sudo mkdir -p /var/run/postgresql
sudo chown postgres:postgres /var/run/postgresql

# Start PostgreSQL
sudo -u postgres /usr/bin/postgres -D /var/lib/postgresql/data &
```

### 3. Create Database and User

```bash
# Create database user and database
sudo -u postgres psql << EOF
CREATE USER passport_scorer WITH PASSWORD 'devpassword123';
CREATE DATABASE passport_scorer_dev OWNER passport_scorer;
ALTER USER passport_scorer CREATEDB;
EOF

# Configure authentication (add to pg_hba.conf)
host    passport_scorer_dev    passport_scorer    127.0.0.1/32    md5
host    passport_scorer_dev    passport_scorer    ::1/128         md5
```

### 4. Setup Django Application

```bash
cd api

# Install Python dependencies
poetry install

# Set environment variables
export DATABASE_URL="postgresql://passport_scorer:devpassword123@localhost:5432/passport_scorer_dev"

# Run Django migrations
poetry run python manage.py migrate

# Create test data (optional)
poetry run python ../create_test_data.py
```

### 5. Setup Rust Scorer with SQLX

```bash
cd rust-scorer

# Install sqlx-cli
cargo install sqlx-cli --no-default-features --features postgres

# Create .env file
echo 'DATABASE_URL=postgresql://passport_scorer:devpassword123@localhost:5432/passport_scorer_dev' > .env

# Build with SQLX compile-time checking
cargo build

# Generate SQLX offline data (for CI/CD)
cargo sqlx prepare
```

## Environment Variables

Create a `.env.development` file in the project root:

```bash
# Database Configuration
DATABASE_URL=postgresql://passport_scorer:devpassword123@localhost:5432/passport_scorer_dev
READ_REPLICA_0_URL=postgresql://passport_scorer:devpassword123@localhost:5432/passport_scorer_dev
READ_REPLICA_ANALYTICS_URL=postgresql://passport_scorer:devpassword123@localhost:5432/passport_scorer_dev
DATA_MODEL_DATABASE_URL=postgresql://passport_scorer:devpassword123@localhost:5432/passport_scorer_dev

# Django Configuration
SECRET_KEY=dev-secret-key-not-for-production
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1

# API Configuration
SCORER_SERVER_URL=http://localhost:8000
INTERNAL_API_KEY=dev-internal-api-key

# Feature Flags
FF_MULTI_NULLIFIER=off
FF_DEDUP_EXPIRATION=on

# Rust Configuration
RUST_LOG=debug
RUST_BACKTRACE=1
```

## Test Data

The setup script creates:
- **Test User**: `testuser` / Django admin: `admin/admin`
- **Test Account**: `0x1111111111111111111111111111111111111111`
- **Communities**: IDs 1, 2, 3 with scorers configured
- **API Keys**: Generated during setup (save these!)

## Common Issues and Solutions

### PostgreSQL Won't Start
```bash
# Ensure runtime directory exists
sudo mkdir -p /var/run/postgresql
sudo chown postgres:postgres /var/run/postgresql

# Check logs
sudo tail -f /var/lib/postgresql/data/log/postgresql-*.log
```

### Django Migration Issues
If migrations show as applied but tables don't exist:
```bash
# Option 1: Re-run with syncdb
poetry run python manage.py migrate --run-syncdb

# Option 2: Manually create missing columns
psql -U passport_scorer -d passport_scorer_dev
ALTER TABLE <table_name> ADD COLUMN <column_name> <type>;
```

### SQLX Compilation Errors
```bash
# Ensure DATABASE_URL is set
export DATABASE_URL="postgresql://passport_scorer:devpassword123@localhost:5432/passport_scorer_dev"

# Verify database connection
psql $DATABASE_URL -c "SELECT 1"

# Check that all required tables exist
psql $DATABASE_URL -c "\dt"
```

## Development Workflow

### Start PostgreSQL (if stopped)
```bash
./start-postgres.sh
```

### Run Django Development Server
```bash
cd api
source ../.env.development
poetry run python manage.py runserver
```

### Run Rust Scorer
```bash
cd rust-scorer
source ../.env.development
cargo run
```

### Run Tests
```bash
# Django tests
cd api
poetry run pytest

# Rust tests
cd rust-scorer
cargo test
```

## Database Schema

Key tables created:
- `account_*` - User accounts and API keys
- `scorer_weighted_*` - Scorer configurations
- `registry_*` - Passports, scores, stamps, events
- `ceramic_cache_*` - Cached credential data
- `registry_humanpoints*` - Human points tracking

## Additional Scripts

- `install.sh` - Basic dependency installation
- `setup-dev.sh` - Full setup with systemd
- `setup-dev-container.sh` - Setup for container environments
- `create_test_data.py` - Creates test data using Django ORM
- `start-postgres.sh` - Helper to start PostgreSQL

## Support

For issues or questions:
1. Check the logs in `/var/lib/postgresql/data/log/`
2. Verify environment variables are set correctly
3. Ensure all services are running (`pgrep postgres`)
4. Check Django migration status: `poetry run python manage.py showmigrations`

## Next Steps

1. Review the Rust scorer implementation in `rust-scorer/`
2. Test the API endpoints with the generated API keys
3. Monitor performance differences between Python and Rust implementations
4. Configure your IDE for both Python and Rust development