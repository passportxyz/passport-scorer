#!/bin/bash

# Simple script to start Redis/Valkey in container environments

set -e

REDIS_HOST="localhost"
REDIS_PORT="6379"

# Function to check if a command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Determine which server binary to use
REDIS_BIN=""
if command_exists valkey-server; then
    REDIS_BIN="valkey-server"
elif command_exists redis-server; then
    REDIS_BIN="redis-server"
else
    echo "Error: Neither valkey-server nor redis-server found"
    exit 1
fi

# Check if already running
if pgrep -x redis-server >/dev/null || pgrep -x valkey-server >/dev/null; then
    echo "$REDIS_BIN is already running"
    exit 0
fi

# Determine which CLI to use
REDIS_CLI=""
if command_exists valkey-cli; then
    REDIS_CLI="valkey-cli"
elif command_exists redis-cli; then
    REDIS_CLI="redis-cli"
else
    echo "Error: Neither valkey-cli nor redis-cli found"
    exit 1
fi

# Start the server
echo "Starting $REDIS_BIN..."
$REDIS_BIN --daemonize yes --bind 127.0.0.1 --port ${REDIS_PORT}
sleep 3

# Verify it's running
if $REDIS_CLI -h ${REDIS_HOST} -p ${REDIS_PORT} ping >/dev/null 2>&1; then
    echo "$REDIS_BIN started successfully"
else
    echo "Error: $REDIS_BIN failed to start"
    exit 1
fi
