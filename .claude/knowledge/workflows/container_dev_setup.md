# Container/Ubuntu Development Setup

## Overview

Three setup scripts exist for Ubuntu/Debian/container environments alongside the original Fedora scripts.

## Scripts

### 1. install-ubuntu-container.sh
For containers without root access (e.g., Node.js base images running as 'node' user).

Uses micromamba for all dependencies:
- python=3.12, postgresql=14, redis-server, gcc, g++, make, pkg-config, openssl, libpq
- Creates symlink: `ar -> x86_64-conda-linux-gnu-ar` (needed by ring crate)
- Installs Poetry via pip in micromamba env
- Installs Rust via rustup (installs to ~/.cargo)

PostgreSQL runs in userspace at ~/pgdata (no postgres system user needed).
Redis runs daemonized: `redis-server --daemonize yes --bind 127.0.0.1`

Key environment variables for Rust compilation:
- CC=$CONDA_PREFIX/bin/gcc
- AR=$CONDA_PREFIX/bin/ar
- LIBRARY_PATH, LD_LIBRARY_PATH, C_INCLUDE_PATH, PKG_CONFIG_PATH pointing to $CONDA_PREFIX
- SQLX_OFFLINE=true (uses cached .sqlx/ queries)

Activation helper: `source ~/activate-passport-dev.sh`

### 2. setup-ubuntu.sh
Database setup, Django migrations, test data creation. Works with micromamba-installed PostgreSQL running in userspace.

### 3. install-ubuntu.sh
For Ubuntu systems with sudo/apt access (standard installs).

## Environment Detection Pattern

The scripts detect container vs systemd environments and adjust PostgreSQL/Redis startup accordingly. Container environments use direct binary execution with `--daemonize` instead of systemctl.

See: `dev-setup/install-ubuntu-container.sh`, `dev-setup/setup-ubuntu.sh`, `dev-setup/install-ubuntu.sh`
