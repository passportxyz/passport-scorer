#!/bin/bash
# Install basic dependencies for Ubuntu/Debian - called by setup-ubuntu.sh or can be run standalone

set -e

# Only show header if run directly (not sourced)
if [ "${BASH_SOURCE[0]}" == "${0}" ]; then
    echo "=== Installing basic dependencies ==="
fi

# Update package list
sudo apt-get update

# Install system packages
sudo apt-get install -y \
    python3.12 \
    python3.12-dev \
    python3.12-venv \
    python3-pip \
    postgresql \
    postgresql-contrib \
    gcc \
    libssl-dev \
    pkg-config \
    git \
    curl \
    build-essential \
    libpq-dev || true

# Install Redis (Valkey not in Debian repos, use Redis)
if ! command -v redis-server >/dev/null 2>&1; then
    sudo apt-get install -y redis-server || true
fi

# Install Poetry
if ! command -v poetry >/dev/null 2>&1; then
    curl -sSL https://install.python-poetry.org | python3.12 -
    export PATH="$HOME/.local/bin:$PATH"
    echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bashrc
fi

# Install Rust
if ! command -v cargo >/dev/null 2>&1; then
    curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y
    source "$HOME/.cargo/env"
fi

# Only show footer if run directly
if [ "${BASH_SOURCE[0]}" == "${0}" ]; then
    echo "Basic dependencies installed!"
fi
