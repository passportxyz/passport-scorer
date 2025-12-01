### [19:44] [dependency] Valkey/Redis requirement for dev setup
**Details**: Django's caching system requires Redis/Valkey to be running for the development environment. The CACHES setting in api/scorer/settings/base.py uses django.core.cache.backends.redis.RedisCache with location from CELERY_BROKER_URL (defaults to redis://localhost:6379/0).

The docker-compose.yml includes a Redis service, but the local dev setup script (dev-setup/setup.sh) was missing Redis/Valkey installation and startup.

Added to dev setup:
- Install valkey or redis package via dnf (Valkey is the Redis fork that Fedora is adopting)
- Start server with: valkey-server --daemonize yes --bind 127.0.0.1 --port 6379
- Add CELERY_BROKER_URL=redis://localhost:6379/0 to .env.development
- Created start-redis.sh helper script for restarting the service

The setup works in container environments without systemctl - just uses the binary directly with --daemonize flag.
**Files**: dev-setup/setup.sh, dev-setup/install.sh, dev-setup/start-redis.sh, api/scorer/settings/base.py, docker-compose.yml
---

