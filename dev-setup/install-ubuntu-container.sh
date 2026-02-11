#!/bin/bash
# Install basic dependencies for containers without root/sudo access
# Uses micromamba for userspace package management
#
# This script handles minimal containers (e.g., Node.js base images)
# that don't have Python, PostgreSQL, Redis, or build tools.

set -e

MAMBA_ROOT="${MAMBA_ROOT_PREFIX:-$HOME/micromamba}"
MAMBA_BIN="${MAMBA_EXE:-$HOME/bin/micromamba}"
ENV_NAME="passport-dev"

# Only show header if run directly (not sourced)
if [ "${BASH_SOURCE[0]}" == "${0}" ]; then
    echo "=== Installing basic dependencies (container/userspace mode) ==="
fi

# Install micromamba if not present
if [ ! -f "$MAMBA_BIN" ]; then
    echo "Installing micromamba..."
    mkdir -p "$(dirname "$MAMBA_BIN")"
    curl -Ls "https://github.com/mamba-org/micromamba-releases/releases/latest/download/micromamba-linux-64" \
        -o "$MAMBA_BIN"
    chmod +x "$MAMBA_BIN"
fi

export MAMBA_EXE="$MAMBA_BIN"
export MAMBA_ROOT_PREFIX="$MAMBA_ROOT"

# Create environment with Python, PostgreSQL, Redis, and build tools
if ! "$MAMBA_BIN" env list 2>/dev/null | grep -q "$ENV_NAME"; then
    echo "Creating micromamba environment '$ENV_NAME'..."
    "$MAMBA_BIN" create -n "$ENV_NAME" -c conda-forge \
        python=3.12 \
        postgresql=14 \
        redis-server \
        gcc \
        gxx \
        make \
        pkg-config \
        openssl \
        libpq \
        -y
else
    echo "Environment '$ENV_NAME' already exists"
fi

# Create symlinks for tools that ring/other crates expect
CONDA_PREFIX="$MAMBA_ROOT/envs/$ENV_NAME"
if [ ! -f "$CONDA_PREFIX/bin/ar" ]; then
    ln -sf "$CONDA_PREFIX/bin/x86_64-conda-linux-gnu-ar" "$CONDA_PREFIX/bin/ar" 2>/dev/null || true
fi

# Install Poetry via pip in the environment
eval "$("$MAMBA_BIN" shell hook --shell bash)"
micromamba activate "$ENV_NAME"

if ! command -v poetry >/dev/null 2>&1; then
    echo "Installing Poetry..."
    pip install poetry
fi

# Install Rust (installs to ~/.cargo, no root needed)
if ! command -v cargo >/dev/null 2>&1; then
    echo "Installing Rust..."
    curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y
    source "$HOME/.cargo/env"
fi

# Write activation helper
cat > "$HOME/activate-passport-dev.sh" << 'ACTIVATE_EOF'
#!/bin/bash
# Source this file to activate the passport-scorer dev environment
# Usage: source ~/activate-passport-dev.sh

export MAMBA_EXE="${MAMBA_EXE:-$HOME/bin/micromamba}"
export MAMBA_ROOT_PREFIX="${MAMBA_ROOT_PREFIX:-$HOME/micromamba}"

eval "$($MAMBA_EXE shell hook --shell bash)"
micromamba activate passport-dev

# Cargo/Rust
[ -f "$HOME/.cargo/env" ] && source "$HOME/.cargo/env"

# Build environment for native extensions (ring, openssl, etc.)
export CC="$CONDA_PREFIX/bin/gcc"
export AR="$CONDA_PREFIX/bin/ar"
export LIBRARY_PATH="$CONDA_PREFIX/lib:$LIBRARY_PATH"
export LD_LIBRARY_PATH="$CONDA_PREFIX/lib:$LD_LIBRARY_PATH"
export C_INCLUDE_PATH="$CONDA_PREFIX/include:$C_INCLUDE_PATH"
export PKG_CONFIG_PATH="$CONDA_PREFIX/lib/pkgconfig:$PKG_CONFIG_PATH"

# SQLX offline mode (uses cached queries)
export SQLX_OFFLINE=true

echo "Passport-scorer dev environment activated"
ACTIVATE_EOF
chmod +x "$HOME/activate-passport-dev.sh"

# Only show footer if run directly
if [ "${BASH_SOURCE[0]}" == "${0}" ]; then
    echo ""
    echo "Basic dependencies installed!"
    echo "Activate with: source ~/activate-passport-dev.sh"
fi
