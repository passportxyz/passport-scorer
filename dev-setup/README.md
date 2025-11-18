# Development Environment Setup

Quick setup scripts for the Passport Scorer development environment with PostgreSQL, Django, and Rust/SQLX support.

## 🚀 Quick Start

```bash
# From the project root, run the main setup script
./dev-setup/setup.sh
```

This single script automatically:
- Detects your environment (container vs system with systemd)
- Installs all dependencies (PostgreSQL, Python, Poetry, Rust, SQLX)
- Configures PostgreSQL database
- Runs Django migrations
- Creates test data with API keys
- Sets up SQLX for Rust development

## 📁 Script Structure

```
dev-setup/
├── setup.sh              # Main setup script (use this!)
├── install.sh            # Basic dependency installer (called by setup.sh)
├── create_test_data.py   # Django test data creation (called by setup.sh)
├── start-postgres.sh     # Helper to restart PostgreSQL if needed
└── README.md            # This file
```

### Why This Structure?

- **One main script**: `setup.sh` handles everything
- **Modular components**: Individual scripts can be called if needed
- **No duplication**: Scripts call each other instead of duplicating code
- **Environment aware**: Automatically detects container vs system environment

## 🔧 Individual Scripts

### setup.sh
The main script that orchestrates everything. It:
- Detects if you're in a container (no systemd) or regular system
- Calls `install.sh` for dependencies
- Sets up PostgreSQL appropriately for your environment
- Runs Django migrations
- Calls `create_test_data.py` for test data
- Configures SQLX

### install.sh
Installs basic dependencies only:
- Python 3.12 + Poetry
- PostgreSQL packages
- Rust toolchain
- Build dependencies

Can be run standalone if you only need dependencies.

### create_test_data.py
Creates test data using Django ORM:
- Test user and account
- 3 communities with scorers
- API keys for testing
- Sample stamps (if ceramic_cache table exists)

### start-postgres.sh
Simple helper to restart PostgreSQL in container environments where systemd isn't available.

## 🗄️ Database Details

- **Database**: `passport_scorer_dev`
- **User**: `passport_scorer`
- **Password**: `devpassword123`
- **Host**: `localhost:5432`

## 🔑 Test Data Created

- **Django Admin**: `admin` / `admin`
- **Test User**: `testuser`
- **Communities**: IDs 1, 2, 3 with scorers
- **API Keys**: Generated during setup (save these!)

## 🐛 Troubleshooting

### PostgreSQL Won't Start
```bash
# In containers, use:
./dev-setup/start-postgres.sh

# Check logs:
sudo tail -f /var/lib/postgresql/data/log/postgresql-*.log
```

### SQLX Compilation Issues
```bash
# Ensure DATABASE_URL is set:
export DATABASE_URL="postgresql://passport_scorer:devpassword123@localhost:5432/passport_scorer_dev"

# Verify with:
sqlx database setup
```

### Missing Tables
If Django migrations show as applied but tables don't exist:
```bash
cd api
poetry run python manage.py migrate --run-syncdb
```

## 🔄 Development Workflow

After setup completes:

```bash
# 1. Source the environment
source .env.development

# 2. Start Django server
cd api && poetry run python manage.py runserver

# 3. In another terminal, run Rust scorer
cd rust-scorer && cargo run
```

## 📝 Environment Variables

The setup creates `.env.development` with all necessary variables. Key ones:
- `DATABASE_URL` - PostgreSQL connection string
- `INTERNAL_API_KEY` - For internal API calls
- `RUST_LOG=debug` - Rust logging level
- `FF_MULTI_NULLIFIER=off` - Feature flags

## ✅ What Gets Installed

- **Python 3.12** with Poetry package manager
- **PostgreSQL** database server
- **Rust** toolchain with cargo
- **SQLX CLI** for database operations
- **Build tools**: gcc, openssl-devel, pkg-config
- **Django** dependencies via Poetry
- **Test data** including API keys and scorers