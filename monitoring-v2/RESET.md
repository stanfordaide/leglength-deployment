# Reset from Monitoring v1 to Monitoring v2

## Steps to Reset

### 1. Stop Old Monitoring (v1)
```bash
cd /dataNAS/people/arogya/projects/leglength-deployment
cd monitoring && sudo docker compose down
```

### 2. Clean Up Old Monitoring Containers/Volumes (Optional)
```bash
# Remove old monitoring containers and volumes
cd monitoring && sudo docker compose down -v
```

### 3. Set Up Monitoring v2
```bash
cd /dataNAS/people/arogya/projects/leglength-deployment/monitoring-v2
make setup
```

### 4. Start Monitoring v2
```bash
# From project root
make monitoring-start

# Or from monitoring-v2 directory
cd monitoring-v2 && make start
```

### 5. Verify
```bash
make monitoring-status
```

## Quick Reset (All in One)

```bash
# Stop old monitoring
cd monitoring && sudo docker compose down

# Set up and start new monitoring
cd ../monitoring-v2 && make setup && make start

# Verify
cd .. && make monitoring-status
```

## What Gets Reset

- **Old monitoring stack** (`monitoring/`): Stopped and optionally removed
- **Monitoring v2** (`monitoring-v2/`): Fresh setup with:
  - New `.env` file (from template)
  - New data directories
  - Fresh containers

## Ports

Both use the same ports (9032, 9033, 9038), so you can't run both simultaneously. The reset ensures v1 is stopped before v2 starts.
