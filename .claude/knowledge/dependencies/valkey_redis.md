# Valkey/Redis Requirement for Development

## Overview

Django's caching system requires Redis/Valkey to be running for the development environment.

## Configuration

The CACHES setting in `api/scorer/settings/base.py` uses:
- `django.core.cache.backends.redis.RedisCache`
- Location from `CELERY_BROKER_URL` (defaults to `redis://localhost:6379/0`)

## Docker vs Local Development

**Docker**: The docker-compose.yml includes a Redis service that starts automatically.

**Local Development**: Requires manual installation and startup:

### Installation (Fedora/RHEL)
```bash
# Valkey is the Redis fork that Fedora is adopting
sudo dnf install -y valkey || sudo dnf install -y redis
```

### Starting the Server
```bash
# Works in container environments without systemctl
valkey-server --daemonize yes --bind 127.0.0.1 --port 6379
```

### Environment Configuration
Add to `.env.development`:
```bash
CELERY_BROKER_URL=redis://localhost:6379/0
```

## Helper Scripts

- `dev-setup/start-redis.sh` - Helper script for starting/restarting the service
- Uses `--daemonize` flag to run in background without requiring systemd

See: `dev-setup/setup.sh`, `dev-setup/install.sh`, `dev-setup/start-redis.sh`, `api/scorer/settings/base.py`, `docker-compose.yml`
