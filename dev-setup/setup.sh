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
PYTHON_VERSION="3.12"
PGDATA="/var/lib/postgresql/data"
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

echo -e "${GREEN}=== Passport Scorer Development Environment Setup ===${NC}"

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

# Detect if we're in a container environment (no systemd)
detect_environment() {
    if [ -f /.dockerenv ] || [ -f /run/.containerenv ] || ! pidof systemd >/dev/null 2>&1; then
        echo "container"
    else
        echo "system"
    fi
}

ENVIRONMENT=$(detect_environment)
print_status "Detected environment: $ENVIRONMENT"

# 1. Install basic dependencies
print_status "Installing basic dependencies..."
if [ -f "$SCRIPT_DIR/install.sh" ]; then
    source "$SCRIPT_DIR/install.sh"
else
    # Inline basic deps if install.sh doesn't exist
    sudo dnf install -y python3.12 python3.12-devel postgresql postgresql-server postgresql-contrib gcc openssl-devel pkg-config git curl || true

    # Install Poetry if not present
    if ! command_exists poetry; then
        curl -sSL https://install.python-poetry.org | python3.12 -
        export PATH="$HOME/.local/bin:$PATH"
    fi

    # Install Rust if not present
    if ! command_exists cargo; then
        curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y
        source "$HOME/.cargo/env"
    fi
fi

# 2. Setup PostgreSQL based on environment
print_status "Setting up PostgreSQL..."

# Create postgres user if needed
if ! id -u postgres >/dev/null 2>&1; then
    sudo useradd -r -s /bin/bash postgres
fi

# Create data directory
if [ ! -d "$PGDATA" ]; then
    sudo mkdir -p "$PGDATA"
    sudo chown postgres:postgres "$PGDATA"
fi

# Create runtime directory (always needed for Unix socket)
if [ ! -d "/var/run/postgresql" ]; then
    sudo mkdir -p /var/run/postgresql
    sudo chown postgres:postgres /var/run/postgresql
fi

# Initialize database if needed
if [ ! -f "$PGDATA/PG_VERSION" ]; then
    print_status "Initializing PostgreSQL database..."
    sudo -u postgres /usr/bin/initdb -D "$PGDATA"
    print_success "Database initialized"
fi

# Start PostgreSQL based on environment
if ! pgrep -x postgres >/dev/null; then
    if [ "$ENVIRONMENT" = "container" ]; then
        print_status "Starting PostgreSQL (container mode)..."
        sudo -u postgres /usr/bin/postgres -D "$PGDATA" > /tmp/postgres.log 2>&1 &
        sleep 3
    else
        print_status "Starting PostgreSQL (system mode)..."
        sudo systemctl start postgresql
        sudo systemctl enable postgresql
    fi
fi

# Wait for PostgreSQL to be ready
print_status "Waiting for PostgreSQL..."
for i in {1..30}; do
    if sudo -u postgres psql -c "SELECT 1" >/dev/null 2>&1; then
        print_success "PostgreSQL is ready"
        break
    fi
    if [ $i -eq 30 ]; then
        print_error "PostgreSQL failed to start"
        exit 1
    fi
    sleep 1
done

# 3. Create database and user
print_status "Setting up database..."

sudo -u postgres psql <<EOF 2>/dev/null || true
DO \$\$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_user WHERE usename = '${DB_USER}') THEN
        CREATE USER ${DB_USER} WITH PASSWORD '${DB_PASSWORD}';
    END IF;
END
\$\$;

SELECT 'CREATE DATABASE ${DB_NAME} OWNER ${DB_USER}'
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = '${DB_NAME}')\\gexec;

GRANT ALL PRIVILEGES ON DATABASE ${DB_NAME} TO ${DB_USER};
ALTER USER ${DB_USER} CREATEDB;
EOF

print_success "Database ${DB_NAME} ready"

# 4. Configure PostgreSQL authentication
print_status "Configuring PostgreSQL authentication..."
PG_HBA="$PGDATA/pg_hba.conf"
if ! sudo grep -q "host.*${DB_NAME}.*${DB_USER}.*md5" "$PG_HBA" 2>/dev/null; then
    sudo -u postgres bash -c "cat >> $PG_HBA" <<EOF

# Added by setup script
host    ${DB_NAME}    ${DB_USER}    127.0.0.1/32    md5
host    ${DB_NAME}    ${DB_USER}    ::1/128         md5
EOF
    sudo -u postgres psql -c "SELECT pg_reload_conf();" >/dev/null 2>&1
fi

# 5. Setup environment file
export DATABASE_URL="postgresql://${DB_USER}:${DB_PASSWORD}@${DB_HOST}:${DB_PORT}/${DB_NAME}"

if [ ! -f "$PROJECT_ROOT/.env.development" ]; then
    print_status "Creating .env.development..."
    cat > "$PROJECT_ROOT/.env.development" <<EOL
# Database Configuration
DATABASE_URL=${DATABASE_URL}
READ_REPLICA_0_URL=${DATABASE_URL}
READ_REPLICA_ANALYTICS_URL=${DATABASE_URL}
DATA_MODEL_DATABASE_URL=${DATABASE_URL}

# Django Configuration
SECRET_KEY=dev-secret-key-$(openssl rand -hex 32)
DEBUG=True
ALLOWED_HOSTS='["localhost","127.0.0.1"]'

# API Configuration
SCORER_SERVER_URL=http://localhost:8000
INTERNAL_API_KEY=dev-internal-api-$(openssl rand -hex 16)

# Rust Configuration
RUST_LOG=debug
RUST_BACKTRACE=1

# Feature Flags
FF_MULTI_NULLIFIER=off
HUMAN_POINTS_ENABLED=false

# Required for didkit (Rust credential validation library)
# Run: ulimit -n 4096
EOL
    print_success ".env.development created"
fi

# Set file descriptor limit for didkit (needs many open files)
print_status "Setting file descriptor limit..."
ulimit -n 4096 2>/dev/null && print_success "File descriptor limit set to 4096" || print_error "Could not set ulimit (run manually: ulimit -n 4096)"

# Source environment
set -a
source "$PROJECT_ROOT/.env.development"
set +a

# 6. Install Python dependencies
print_status "Installing Python dependencies..."
cd "$PROJECT_ROOT/api"
poetry install
cd "$PROJECT_ROOT"
print_success "Python dependencies installed"

# 7. Run Django migrations
print_status "Running Django migrations..."
cd "$PROJECT_ROOT/api"
poetry run python manage.py migrate --database default
cd "$PROJECT_ROOT"
print_success "Django migrations completed"

# 8. Create test data
print_status "Creating test data..."
cd "$PROJECT_ROOT/api"

# Base test data (scorers, API keys, etc.)
if [ -f "$SCRIPT_DIR/create_test_data.py" ]; then
    poetry run python "$SCRIPT_DIR/create_test_data.py"
    print_success "Base test data created"
else
    print_error "Test data script not found"
fi

# Comparison test data (bans, stakes, CGrants, etc.)
if [ -f "$SCRIPT_DIR/create_comparison_test_data.py" ]; then
    print_status "Creating comparison test data..."
    poetry run python "$SCRIPT_DIR/create_comparison_test_data.py"
    print_success "Comparison test data created"
else
    print_error "Comparison test data script not found"
fi

cd "$PROJECT_ROOT"

# 9. Setup SQLX for Rust
if [ -d "$PROJECT_ROOT/rust-scorer" ]; then
    print_status "Setting up SQLX..."

    # Install sqlx-cli if needed
    if ! command_exists sqlx; then
        print_status "Installing sqlx-cli..."
        cargo install sqlx-cli --no-default-features --features postgres,rustls
        print_success "sqlx-cli installed"
    fi

    # Create .env for rust-scorer
    echo "DATABASE_URL=${DATABASE_URL}" > "$PROJECT_ROOT/rust-scorer/.env"

    # Generate offline data
    cd "$PROJECT_ROOT/rust-scorer"
    cargo sqlx prepare 2>/dev/null || true
    cd "$PROJECT_ROOT"
    print_success "SQLX environment ready"
fi

# 10. Generate test credentials for comparison tests
if [ -d "$PROJECT_ROOT/rust-scorer/comparison-tests" ]; then
    print_status "Generating test credentials for comparison tests..."

    # Increase file descriptor limit (didkit needs many open files)
    ulimit -n 4096 2>/dev/null || true

    cd "$PROJECT_ROOT/rust-scorer/comparison-tests"
    cargo run --bin gen-credentials --release 2>/dev/null || {
        print_error "Failed to generate credentials (this is optional)"
        cd "$PROJECT_ROOT"
    }

    if [ -f "$PROJECT_ROOT/rust-scorer/comparison-tests/test_config.json" ]; then
        print_success "Test credentials generated"
    fi

    cd "$PROJECT_ROOT"
fi

# 11. Final verification
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
echo ""
if [ "$ENVIRONMENT" = "container" ]; then
    echo "To restart PostgreSQL if needed:"
    echo "  $SCRIPT_DIR/start-postgres.sh"
fi
echo ""
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