# Reset from Monitoring v1 to Monitoring v2

## Steps to Reset (Following CHANGES.md workflow)

### 1. Generate Configuration from Template
```bash
cd /dataNAS/people/arogya/projects/leglength-deployment
sudo make setup
```
This generates `monitoring-v2/.env` from `config.env.template` (as per CHANGES.md).

### 2. Stop Old Monitoring (v1)
```bash
cd monitoring && sudo docker compose down
```

### 3. Start Monitoring v2
```bash
# From project root (recommended)
make monitoring-start

# Or from monitoring-v2 directory
cd monitoring-v2 && make start
```

### 4. Verify
```bash
make monitoring-status
```

## Quick Reset (All in One)

```bash
# From project root
cd /dataNAS/people/arogya/projects/leglength-deployment

# 1. Generate configs (creates monitoring-v2/.env)
sudo make setup

# 2. Stop old monitoring
cd monitoring && sudo docker compose down && cd ..

# 3. Start monitoring-v2
make monitoring-start

# 4. Verify
make monitoring-status
```

## Using the Reset Command

From `monitoring-v2/` directory:
```bash
cd monitoring-v2
make reset
```

This will:
1. Stop old monitoring (v1)
2. Stop monitoring-v2 if running
3. Check that .env exists (from `make setup`)
4. Create data directories
5. Start monitoring-v2

## What Gets Reset

- **Old monitoring stack** (`monitoring/`): Stopped and optionally removed
- **Monitoring v2** (`monitoring-v2/`): Fresh setup with:
  - New `.env` file (from template)
  - New data directories
  - Fresh containers

## Ports

Both use the same ports (9032, 9033, 9038), so you can't run both simultaneously. The reset ensures v1 is stopped before v2 starts.
