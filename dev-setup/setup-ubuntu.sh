#!/bin/bash

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
DB_NAME="passport_scorer_dev"
DB_USER="passport_scorer"
DB_PASSWORD="devpassword123"
DB_HOST="localhost"
DB_PORT="5432"
REDIS_HOST="localhost"
REDIS_PORT="6379"
PYTHON_VERSION="3.12"
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

echo -e "${GREEN}=== Passport Scorer Development Environment Setup (Ubuntu/Debian) ===${NC}"

# Function to check if a command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Function to print status
print_status() {
    echo -e "${YELLOW}>>> $1${NC}"
}

print_success() {
    echo -e "${GREEN}✓ $1${NC}"
}

print_error() {
    echo -e "${RED}✗ $1${NC}"
}

# Detect environment type
detect_environment() {
    if command_exists sudo; then
        echo "sudo"
    elif [ "$(id -u)" -eq 0 ]; then
        echo "root"
    else
        echo "userspace"
    fi
}

ENVIRONMENT=$(detect_environment)
print_status "Detected environment: $ENVIRONMENT"

# 1. Install basic dependencies based on environment
print_status "Installing basic dependencies..."

if [ "$ENVIRONMENT" = "userspace" ]; then
    # No root/sudo - use micromamba for everything
    if [ -f "$SCRIPT_DIR/install-ubuntu-container.sh" ]; then
        source "$SCRIPT_DIR/install-ubuntu-container.sh"
    else
        print_error "install-ubuntu-container.sh not found"
        exit 1
    fi

    # Activate micromamba environment for the rest of setup
    export MAMBA_EXE="${MAMBA_EXE:-$HOME/bin/micromamba}"
    export MAMBA_ROOT_PREFIX="${MAMBA_ROOT_PREFIX:-$HOME/micromamba}"
    eval "$($MAMBA_EXE shell hook --shell bash)"
    micromamba activate passport-dev

    # Set build environment
    export CC="$CONDA_PREFIX/bin/gcc"
    export AR="$CONDA_PREFIX/bin/ar"
    export LIBRARY_PATH="$CONDA_PREFIX/lib:${LIBRARY_PATH:-}"
    export LD_LIBRARY_PATH="$CONDA_PREFIX/lib:${LD_LIBRARY_PATH:-}"
    export C_INCLUDE_PATH="$CONDA_PREFIX/include:${C_INCLUDE_PATH:-}"
    export PKG_CONFIG_PATH="$CONDA_PREFIX/lib/pkgconfig:${PKG_CONFIG_PATH:-}"
    export SQLX_OFFLINE=true

    [ -f "$HOME/.cargo/env" ] && source "$HOME/.cargo/env"

    PGDATA="$HOME/pgdata"
else
    # Has root/sudo access - use system packages
    if [ -f "$SCRIPT_DIR/install-ubuntu.sh" ]; then
        source "$SCRIPT_DIR/install-ubuntu.sh"
    else
        sudo apt-get update
        sudo apt-get install -y \
            python3.12 python3.12-dev python3.12-venv python3-pip \
            postgresql postgresql-contrib \
            gcc libssl-dev pkg-config git curl build-essential libpq-dev \
            redis-server || true

        if ! command_exists poetry; then
            curl -sSL https://install.python-poetry.org | python3.12 -
            export PATH="$HOME/.local/bin:$PATH"
        fi

        if ! command_exists cargo; then
            curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y
            source "$HOME/.cargo/env"
        fi
    fi

    # Detect PostgreSQL data directory
    PG_VERSION=$(ls /etc/postgresql/ 2>/dev/null | sort -rn | head -1)
    if [ -n "$PG_VERSION" ]; then
        PGDATA="/var/lib/postgresql/$PG_VERSION/main"
    else
        PGDATA="/var/lib/postgresql/data"
    fi
fi

# 2. Setup PostgreSQL
print_status "Setting up PostgreSQL..."

if [ "$ENVIRONMENT" = "userspace" ]; then
    # Initialize and start PostgreSQL in userspace
    if [ ! -f "$PGDATA/PG_VERSION" ]; then
        mkdir -p "$PGDATA"
        initdb -D "$PGDATA"
        # Add password authentication
        cat >> "$PGDATA/pg_hba.conf" << EOF

# Added by setup script
host    all    all    127.0.0.1/32    md5
host    all    all    ::1/128         md5
EOF
        print_success "PostgreSQL initialized"
    fi

    if ! pgrep -x postgres >/dev/null; then
        pg_ctl -D "$PGDATA" -l "$PGDATA/logfile" start
        sleep 2
    fi

    # Create user and database (we own the cluster as current user)
    psql -d postgres <<EOSQL 2>/dev/null || true
DO \$\$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_user WHERE usename = '${DB_USER}') THEN
        CREATE USER ${DB_USER} WITH PASSWORD '${DB_PASSWORD}';
    END IF;
END
\$\$;
EOSQL

    psql -d postgres -tc "SELECT 1 FROM pg_database WHERE datname = '${DB_NAME}'" | grep -q 1 || \
        psql -d postgres -c "CREATE DATABASE ${DB_NAME} OWNER ${DB_USER};"

    psql -d postgres <<EOSQL 2>/dev/null || true
GRANT ALL PRIVILEGES ON DATABASE ${DB_NAME} TO ${DB_USER};
ALTER USER ${DB_USER} CREATEDB;
EOSQL

else
    # System mode with sudo
    if ! sudo systemctl is-active --quiet postgresql 2>/dev/null; then
        if ! pgrep -x postgres >/dev/null; then
            print_status "Starting PostgreSQL..."
            sudo systemctl start postgresql 2>/dev/null || \
                sudo -u postgres pg_ctl -D "$PGDATA" -l /tmp/postgres.log start
            sudo systemctl enable postgresql 2>/dev/null || true
        fi
    fi

    # Wait for PostgreSQL to be ready
    for i in {1..30}; do
        if sudo -u postgres psql -c "SELECT 1" >/dev/null 2>&1; then
            break
        fi
        [ $i -eq 30 ] && { print_error "PostgreSQL failed to start"; exit 1; }
        sleep 1
    done

    # Create user and database
    sudo -u postgres psql <<EOSQL 2>/dev/null || true
DO \$\$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_user WHERE usename = '${DB_USER}') THEN
        CREATE USER ${DB_USER} WITH PASSWORD '${DB_PASSWORD}';
    END IF;
END
\$\$;
EOSQL

    sudo -u postgres psql -tc "SELECT 1 FROM pg_database WHERE datname = '${DB_NAME}'" | grep -q 1 || \
        sudo -u postgres psql -c "CREATE DATABASE ${DB_NAME} OWNER ${DB_USER};"

    sudo -u postgres psql <<EOSQL 2>/dev/null || true
GRANT ALL PRIVILEGES ON DATABASE ${DB_NAME} TO ${DB_USER};
ALTER USER ${DB_USER} CREATEDB;
EOSQL

    # Configure pg_hba.conf if needed
    PG_HBA="/etc/postgresql/$PG_VERSION/main/pg_hba.conf"
    if [ -f "$PG_HBA" ] && ! sudo grep -q "host.*${DB_NAME}.*${DB_USER}.*md5" "$PG_HBA" 2>/dev/null; then
        sudo bash -c "cat >> $PG_HBA" <<EOF

# Added by setup script
host    ${DB_NAME}    ${DB_USER}    127.0.0.1/32    md5
host    ${DB_NAME}    ${DB_USER}    ::1/128         md5
EOF
        sudo systemctl reload postgresql 2>/dev/null || \
            sudo -u postgres psql -c "SELECT pg_reload_conf();" >/dev/null 2>&1
    fi
fi

# Verify PostgreSQL
print_status "Waiting for PostgreSQL..."
for i in {1..30}; do
    if PGPASSWORD="${DB_PASSWORD}" psql -h ${DB_HOST} -U ${DB_USER} -d ${DB_NAME} -c "SELECT 1" >/dev/null 2>&1; then
        print_success "PostgreSQL is ready (${DB_NAME} @ ${DB_HOST}:${DB_PORT})"
        break
    fi
    [ $i -eq 30 ] && { print_error "PostgreSQL connection failed"; exit 1; }
    sleep 1
done

# 3. Setup and start Redis
print_status "Setting up Redis..."

if ! pgrep -x redis-server >/dev/null; then
    if [ "$ENVIRONMENT" != "userspace" ] && command_exists systemctl; then
        sudo systemctl start redis-server 2>/dev/null || \
            redis-server --daemonize yes --bind 127.0.0.1 --port ${REDIS_PORT}
        sudo systemctl enable redis-server 2>/dev/null || true
    else
        redis-server --daemonize yes --bind 127.0.0.1 --port ${REDIS_PORT}
    fi
    sleep 2
fi

if redis-cli -h ${REDIS_HOST} -p ${REDIS_PORT} ping >/dev/null 2>&1; then
    print_success "Redis is ready"
else
    print_error "Redis failed to start"
    exit 1
fi

# 4. Setup environment file
if [ ! -f "$PROJECT_ROOT/.env.development" ]; then
    print_error ".env.development not found - it should be checked into the repo"
    exit 1
fi

# Set file descriptor limit for didkit (needs many open files)
print_status "Setting file descriptor limit..."
ulimit -n 4096 2>/dev/null && print_success "File descriptor limit set to 4096" || \
    print_error "Could not set ulimit (run manually: ulimit -n 4096)"

# Source environment
set -a
source "$PROJECT_ROOT/.env.development"
set +a

# Create symlink for Django (it reads .env from api directory)
ln -sf "$PROJECT_ROOT/.env.development" "$PROJECT_ROOT/api/.env"

# 5. Install Python dependencies
print_status "Installing Python dependencies..."
cd "$PROJECT_ROOT/api"
poetry install

# Ensure Poetry links to the created virtualenv
VENV_PATH=$(poetry env info --path 2>/dev/null || true)
if [ -z "$VENV_PATH" ] || [ "$VENV_PATH" = "NA" ]; then
    print_status "Linking Poetry to virtualenv..."
    VENV_PYTHON=$(find ~/.cache/pypoetry/virtualenvs -name "python" -path "*/passport-api-*/bin/python" 2>/dev/null | head -1)
    if [ -n "$VENV_PYTHON" ]; then
        poetry env use "$VENV_PYTHON"
        print_success "Poetry virtualenv linked"
    fi
fi

cd "$PROJECT_ROOT"
print_success "Python dependencies installed"

# 6. Run Django migrations
print_status "Running Django migrations..."
cd "$PROJECT_ROOT/api"
poetry run python manage.py migrate --database default
cd "$PROJECT_ROOT"
print_success "Django migrations completed"

# 7. Create test data
print_status "Creating test data..."
cd "$PROJECT_ROOT/api"

if [ -f "$SCRIPT_DIR/create_test_data.py" ]; then
    if poetry run python "$SCRIPT_DIR/create_test_data.py"; then
        print_success "Base test data created"
    else
        print_error "Failed to create base test data"
        exit 1
    fi
else
    print_error "Test data script not found"
    exit 1
fi

if [ -f "$SCRIPT_DIR/create_comparison_test_data.py" ]; then
    print_status "Creating comparison test data..."
    if poetry run python "$SCRIPT_DIR/create_comparison_test_data.py"; then
        print_success "Comparison test data created"
    else
        print_error "Failed to create comparison test data"
        exit 1
    fi
fi

cd "$PROJECT_ROOT"

# 8. Setup SQLX for Rust
if [ -d "$PROJECT_ROOT/rust-scorer" ]; then
    print_status "Setting up SQLX..."

    # Create .env for rust-scorer
    if [[ "${DATABASE_URL}" == *"?sslmode="* ]]; then
        echo "DATABASE_URL=${DATABASE_URL}" > "$PROJECT_ROOT/rust-scorer/.env"
    else
        echo "DATABASE_URL=${DATABASE_URL}?sslmode=disable" > "$PROJECT_ROOT/rust-scorer/.env"
    fi

    print_success "SQLX environment ready"
fi

# 9. Final verification
print_status "Verifying installation..."
if PGPASSWORD="${DB_PASSWORD}" psql -h ${DB_HOST} -U ${DB_USER} -d ${DB_NAME} -c "SELECT 1" >/dev/null 2>&1; then
    print_success "Database connection successful"
else
    print_error "Database connection failed"
fi

# Summary
echo ""
echo -e "${GREEN}=== Setup Complete ===${NC}"
echo ""
echo "Environment: $ENVIRONMENT"
echo "Database: ${DB_NAME} @ ${DB_HOST}:${DB_PORT}"
echo "Redis: ${REDIS_HOST}:${REDIS_PORT}"
echo ""
if [ "$ENVIRONMENT" = "userspace" ]; then
    echo "To activate the dev environment:"
    echo "  source ~/activate-passport-dev.sh"
    echo ""
fi
echo "To start developing:"
echo "  1. Set file descriptor limit: ulimit -n 4096"
echo "  2. Source environment: source .env.development"
echo "  3. Django server: cd api && poetry run python manage.py runserver"
echo "  4. Rust scorer: cd rust-scorer && cargo run"
echo ""
echo "To run comparison tests:"
echo "  ulimit -n 4096"
echo "  cd rust-scorer/comparison-tests && cargo run --release"
echo ""
echo -e "${GREEN}Happy coding!${NC}"
