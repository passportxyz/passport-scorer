#!/bin/bash
# Install basic dependencies - called by setup.sh or can be run standalone

set -e

# Only show header if run directly (not sourced)
if [ "${BASH_SOURCE[0]}" == "${0}" ]; then
    echo "=== Installing basic dependencies ==="
fi

# Install system packages
sudo dnf install -y python3.12 python3.12-devel postgresql postgresql-server postgresql-contrib gcc openssl-devel pkg-config git curl || true

# Install Valkey (Redis fork) - try valkey first, fall back to redis
if ! command -v redis-server >/dev/null 2>&1 && ! command -v valkey-server >/dev/null 2>&1; then
    sudo dnf install -y valkey || sudo dnf install -y redis || true
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

sudo npm install -g agent-browser
agent-browser install --with-deps
