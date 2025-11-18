#!/bin/bash

# Helper script to start PostgreSQL in container environment

PGDATA="/var/lib/postgresql/data"

if ! pgrep -x postgres >/dev/null; then
    echo "Starting PostgreSQL..."
    sudo -u postgres /usr/bin/postgres -D "$PGDATA" &
    sleep 2
    echo "PostgreSQL started"
else
    echo "PostgreSQL is already running"
fi