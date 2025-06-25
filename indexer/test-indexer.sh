#!/bin/bash
# test-indexer.sh - E2E testing script for the indexer using Anvil
#
# This script handles everything needed to test the indexer (except DB/table setup):
#   1. Starts a local Anvil blockchain (you don't need to run Anvil separately)
#   2. Deploys the EventEmitter test contract
#   3. Configures and runs the indexer
#   4. Executes the test suite
#   5. Cleans up everything when done
#
# Prerequisites:
#   - PostgreSQL database with tables already created
#   - Foundry (for Anvil) - install with: curl -L https://foundry.paradigm.xyz | bash
#   - Rust toolchain (for running tests)
#
# Usage:
#   ./test-indexer.sh                                    # Use default DB
#   ./test-indexer.sh "postgresql://user:pass@host/db"  # Custom DB
#   ANVIL_PORT=8546 ./test-indexer.sh                   # Custom port

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
DB_URL="${1:-postgres://passport_scorer:passport_scorer_pwd@localhost:5432/passport_scorer}"
ANVIL_PORT="${ANVIL_PORT:-8545}"

echo -e "${GREEN}🚀 Starting Indexer E2E Tests${NC}"
echo "Configuration:"
echo "  DB_URL: $DB_URL"
echo "  ANVIL_PORT: $ANVIL_PORT"

# Function to cleanup on exit
cleanup() {
    echo -e "${YELLOW}Cleaning up...${NC}"
    if [ ! -z "$ANVIL_PID" ]; then
        kill $ANVIL_PID 2>/dev/null || true
    fi
}
trap cleanup EXIT

# 1. Check if Anvil is installed
if ! command -v anvil &> /dev/null; then
    echo -e "${RED}Error: Anvil not found!${NC}"
    echo "Please install Foundry (which includes Anvil) by running:"
    echo "  curl -L https://foundry.paradigm.xyz | bash"
    echo "  foundryup"
    exit 1
fi

# Check if something is already running on the port
if lsof -Pi :$ANVIL_PORT -sTCP:LISTEN -t >/dev/null 2>&1; then
    echo -e "${RED}Error: Port $ANVIL_PORT is already in use!${NC}"
    echo "Either:"
    echo "  1. Stop the process using port $ANVIL_PORT, or"
    echo "  2. Set a different port: ANVIL_PORT=8546 $0"
    exit 1
fi

# Start Anvil (local Ethereum node for testing)
echo -e "${GREEN}Starting Anvil (local test blockchain) on port $ANVIL_PORT...${NC}"
echo -e "${YELLOW}Note: This script manages Anvil automatically - you don't need to run it separately${NC}"
anvil --port $ANVIL_PORT --block-time 1 --chain-id 10 --silent &
ANVIL_PID=$!

# Wait for Anvil to be ready
echo "Waiting for Anvil to start..."
for i in {1..10}; do
    if curl -s -X POST http://localhost:$ANVIL_PORT -H "Content-Type: application/json" \
        -d '{"jsonrpc":"2.0","method":"eth_chainId","params":[],"id":1}' > /dev/null 2>&1; then
        echo -e "${GREEN}Anvil is ready!${NC}"
        break
    fi
    if [ $i -eq 10 ]; then
        echo -e "${RED}Failed to start Anvil${NC}"
        exit 1
    fi
    sleep 1
done

# 2. Deploy event emitter contract
echo -e "${GREEN}Deploying event emitter contract...${NC}"

# Anvil's default test account #0 (DO NOT USE ON REAL NETWORKS!)
# This is a well-known test private key that comes with Anvil for local development only
# Address: 0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266
ANVIL_TEST_PRIVATE_KEY="0xac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80"

# Check if forge is available (it should be since we need Anvil from Foundry anyway)
if ! command -v forge &> /dev/null; then
    echo -e "${RED}Error: Forge not found!${NC}"
    echo "Forge is part of Foundry (same as Anvil). Please ensure Foundry is properly installed."
    exit 1
fi

# Use forge to compile and deploy
# Get the script directory to use absolute path
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
FORGE_OUTPUT=$(forge create "$SCRIPT_DIR/contracts/test/EventEmitter.sol:EventEmitter" \
    --rpc-url http://localhost:$ANVIL_PORT \
    --private-key $ANVIL_TEST_PRIVATE_KEY \
    --json)
EVENT_EMITTER=$(echo "$FORGE_OUTPUT" | jq -r '.deployedTo')
DEPLOY_TX=$(echo "$FORGE_OUTPUT" | jq -r '.transactionHash')

# Get deployment block number
DEPLOY_BLOCK=$(cast receipt $DEPLOY_TX --rpc-url http://localhost:$ANVIL_PORT --json | jq -r '.blockNumber' | xargs printf "%d")

echo -e "${GREEN}Event emitter deployed at: $EVENT_EMITTER${NC}"
echo -e "${GREEN}Deployment block: $DEPLOY_BLOCK${NC}"

# Set START_BLOCK to deployment block unless overridden
START_BLOCK="${START_BLOCK_OVERRIDE:-$DEPLOY_BLOCK}"

# 3. Export environment variables for indexer
export DB_URL="$DB_URL"
export EVENT_EMITTER="$EVENT_EMITTER"
export INDEXER_OPTIMISM_ENABLED="false"
export INDEXER_ARBITRUM_ENABLED="false"
export INDEXER_BASE_ENABLED="false"
export INDEXER_LINEA_ENABLED="false"
export INDEXER_SCROLL_ENABLED="false"
export INDEXER_ZKSYNC_ENABLED="false"
export INDEXER_SHAPE_ENABLED="false"

# Enable Optimism for testing
export INDEXER_OPTIMISM_ENABLED="true"
export INDEXER_OPTIMISM_RPC_URL="http://localhost:$ANVIL_PORT"
export INDEXER_OPTIMISM_STAKING_CONTRACT="$EVENT_EMITTER"
export INDEXER_OPTIMISM_EAS_CONTRACT="$EVENT_EMITTER"
export INDEXER_OPTIMISM_HUMAN_ID_CONTRACT="$EVENT_EMITTER"
export INDEXER_OPTIMISM_START_BLOCK="$START_BLOCK"

export HUMAN_POINTS_ENABLED="true"

# Parse DB URL for individual components
DB_USER=$(echo $DB_URL | sed -n 's/.*:\/\/\([^:]*\):.*/\1/p')
DB_PASSWORD=$(echo $DB_URL | sed -n 's/.*:\/\/[^:]*:\([^@]*\)@.*/\1/p')
DB_HOST=$(echo $DB_URL | sed -n 's/.*@\([^:\/]*\).*/\1/p')
DB_PORT=$(echo $DB_URL | sed -n 's/.*:\([0-9]*\)\/.*/\1/p')
DB_NAME=$(echo $DB_URL | sed -n 's/.*\/\(.*\)/\1/p')

export DB_USER
export DB_PASSWORD
export DB_HOST
export DB_PORT
export DB_NAME

# 4. Run test scenarios
echo -e "${GREEN}Running test scenarios...${NC}"

# Check if we should run Rust tests or Python scripts
if [ -f "Cargo.toml" ] && grep -q "e2e_tests" Cargo.toml 2>/dev/null; then
    echo "Running Rust E2E tests..."
    cargo test --test e2e_tests -- --test-threads=1 --nocapture
else
    echo "Running test scripts..."
    # Add Python test scripts here if needed
    python3 tests/run_e2e_tests.py
fi

echo -e "${GREEN}✅ All tests completed successfully!${NC}"
