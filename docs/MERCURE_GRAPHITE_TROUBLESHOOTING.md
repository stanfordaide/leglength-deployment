# Mercure ↔ Graphite Communication Troubleshooting

## Error Summary

| Error | Meaning | Typical Cause |
|-------|---------|---------------|
| `[Errno -3] Temporary failure in name resolution` | DNS cannot resolve hostname `graphite` | Graphite container not running, or Mercure/Graphite on different networks |
| `[Errno 111] Connection refused` | Host reachable but nothing listening on port | Wrong port when using host IP, or Graphite not accepting connections |

## Root Causes

### 1. Monitoring Stack Not Running, or Started After Mercure

Graphite runs in the `monitoring-v2` stack. If monitoring is not started, there is no `graphite` container, so Mercure cannot resolve the hostname.

**Startup order matters:** `make start-all` now starts monitoring *before* Mercure so Graphite is available when Mercure tries to connect. If you start services individually, run `make monitoring-start` before `make mercure-start`.

**Check:**
```bash
docker ps | grep graphite
# or
make monitoring-ps
```

**Fix:** Start monitoring before or with Mercure:
```bash
make monitoring-start
# Then restart Mercure to retry connection
make mercure-restart
```

### 2. Wrong Graphite Config (172.17.0.1:2003)

**Problem:** `mercure.json` with `graphite_ip: "172.17.0.1"` and `graphite_port: 2003` is incorrect for Docker deployment.

- `172.17.0.1` = Docker bridge gateway (host from container's perspective)
- Graphite maps **host 9038 → container 2003**, so Carbon listens on **host port 9038**, not 2003
- Connecting to `172.17.0.1:2003` → nothing on host port 2003 → **Connection refused**

**Correct config** (container-to-container on shared network):
```json
"graphite_ip": "graphite",
"graphite_port": 2003
```
Use the **service name** `graphite` and **internal port** `2003` when both Mercure and Graphite are on `leglength-network`.

**Fix:** Regenerate config and copy to installed location:
```bash
make setup
# Verify generated config
grep graphite mercure/config-generated/mercure.json
# Should show: "graphite_ip": "graphite", "graphite_port": 2003

# Config is copied to /opt/mercure/config/ during setup if Mercure is installed
# Restart Mercure to apply
make mercure-restart
```

### 3. Using Host IP – Must Use Host Port

If you must use the host IP (e.g. `172.17.0.1`), use the **host-mapped port**, not the container port:

```json
"graphite_ip": "172.17.0.1",
"graphite_port": 9038
```

Port **9038** is the host port that forwards to Graphite’s internal 2003.

### 4. Networks Not Shared

Mercure and Graphite must be on the same Docker network (`leglength-network`) for the hostname `graphite` to resolve.

**Check:**
```bash
# Ensure network exists
docker network ls | grep leglength-network

# Create if missing
docker network create leglength-network

# Both stacks attach to it (external: true in both compose files)
```

**Verify both containers on same network:**
```bash
docker network inspect leglength-network
# Should list both mercure_router_1 (or similar) and graphite
```

## Quick Fix Checklist

1. **Create network** (if needed): `docker network create leglength-network`
2. **Start monitoring**: `make monitoring-start`
3. **Regenerate config**: `make setup` (sets `graphite_ip: "graphite"`)
4. **Restart Mercure**: `make mercure-restart`
5. **Verify connection**: `docker exec mercure_router_1 ping -c 1 graphite` (or equivalent Mercure container name)

## Diagnostic Commands

```bash
# Is Graphite running?
docker ps --format "table {{.Names}}\t{{.Status}}" | grep graphite

# What config is Mercure using?
sudo cat /opt/mercure/config/mercure.json | grep -E "graphite_ip|graphite_port"

# Can a Mercure container resolve graphite?
docker exec $(docker ps -q -f name=mercure_router) ping -c 1 graphite

# Is Carbon listening inside Graphite container?
docker exec graphite netstat -tlnp | grep 2003
```

## Reference

- **Generated config**: `mercure/config-generated/mercure.json` (from `make setup`)
- **Template**: `mercure/config/mercure.json.template` – uses `${GRAPHITE_IP}` and `${GRAPHITE_PORT}`
- **Setup script**: `scripts/setup-config.sh` – sets `GRAPHITE_IP=graphite`, `GRAPHITE_PORT=2003`
- **Network design**: `NETWORK_ARCHITECTURE.md`
