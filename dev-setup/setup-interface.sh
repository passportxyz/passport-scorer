#!/usr/bin/env bash
# Setup script for the interface (developer portal) frontend
# Installs nvm, Node.js 18, and project dependencies

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
INTERFACE_DIR="$PROJECT_ROOT/interface"
NODE_VERSION=18

echo "=== Interface Frontend Setup ==="

# Install nvm if not present
export NVM_DIR="${NVM_DIR:-$HOME/.nvm}"
if [ ! -s "$NVM_DIR/nvm.sh" ]; then
    echo "Installing nvm..."
    curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.40.1/install.sh | bash
fi
# shellcheck source=/dev/null
. "$NVM_DIR/nvm.sh"

# Install and use Node.js
if ! nvm ls "$NODE_VERSION" &>/dev/null; then
    echo "Installing Node.js $NODE_VERSION..."
    nvm install "$NODE_VERSION"
fi
nvm use "$NODE_VERSION"
echo "Using Node.js $(node --version)"

# Install dependencies
cd "$INTERFACE_DIR"
echo "Installing dependencies..."
NODE_ENV=development yarn install

# Verify setup
echo ""
echo "=== Verifying setup ==="
echo "Node: $(node --version)"
echo "Yarn: $(yarn --version)"
echo "Test files found:"
NODE_ENV=test yarn test --listTests 2>/dev/null | grep -c "\.test\." || true

echo ""
echo "=== Setup complete ==="
echo "To run tests:  cd interface && NODE_ENV=test yarn test"
echo "To run dev:    cd interface && yarn dev"
