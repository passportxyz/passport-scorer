# Container vs System Environment Detection

## The Problem

Development containers (Docker, dev containers) don't have systemd as PID 1, so PostgreSQL must be started differently than on regular systems.

## Container Detection Logic

Checks for:
- /.dockerenv or /run/.containerenv files
- systemd running with `pidof systemd`
- If any indicate container, uses direct postgres command instead of systemctl

## PostgreSQL Startup Commands

**Container mode**:
```bash
sudo -u postgres /usr/bin/postgres -D /var/lib/postgresql/data &
```

**System mode**:
```bash
sudo systemctl start postgresql
```

## Additional Container Requirements

Must create `/var/run/postgresql` directory for Unix socket in containers as it's not created automatically without systemd.

See: `dev-setup/setup.sh`
