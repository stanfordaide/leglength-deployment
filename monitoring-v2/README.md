# Monitoring - Metrics Collection Stack

Standalone monitoring service that collects metrics from Orthanc and Mercure, using Graphite and Prometheus.

## Architecture

```
┌──────────┐         ┌──────────┐         ┌─────────┐
│ Orthanc  │────────▶│Prometheus│◀────────│ Grafana │
│(Prometheus│         │          │         │         │
│ metrics) │         └──────────┘         └─────────┘
└──────────┘                                      ▲
                                                  │
┌──────────┐         ┌──────────┐                │
│ Mercure  │────────▶│ Graphite │────────────────┘
│(Graphite │         │          │
│ metrics) │         └──────────┘
└──────────┘
```

## Services

- **Prometheus** (9033): Scrapes Orthanc's built-in `/tools/metrics-prometheus` endpoint
- **Graphite** (9038): Receives metrics from Mercure (native Graphite support)
- **Grafana** (9032): Visualizes metrics from both Prometheus and Graphite

## Quick Start

```bash
# 1. Setup (generates .env and prometheus.yml from templates)
make setup

# 2. Edit config.env if needed (e.g., DOCKER_HOST_GATEWAY, credentials)
nano config.env

# 3. Regenerate configs if you changed config.env
make setup

# 4. Start services
make start

# 5. Access dashboards
# Grafana: http://localhost:9032 (admin/admin123)
# Prometheus: http://localhost:9033
# Graphite: http://localhost:9041
```

## Configuration

- **`.env`**: Generated from `config.env.template` by `make setup` (contains ports)
- **`config/prometheus/prometheus.yml`**: Generated from `config/prometheus/prometheus.yml.template` by `make setup` (contains Orthanc credentials)
  - **Note**: `prometheus.yml` is gitignored because it contains passwords
  - Always regenerate it with `make setup` after changing `config.env`

## Pre-configured Sources

### Orthanc (via Prometheus)
- Scrapes `http://host.docker.internal:9011/tools/metrics-prometheus`
- Metrics: `orthanc_count_studies`, `orthanc_jobs_completed`, etc.

### Mercure (via Graphite)
- Receives metrics on port 9038 (Carbon line protocol)
- Metrics: `mercure.router.*`, `mercure.dispatcher.*`, etc.

## Makefile Commands

- `make start` - Start all services
- `make stop` - Stop all services
- `make restart` - Restart all services
- `make status` - Check service health
- `make logs` - View logs (use `LOGS_SERVICE=grafana` for specific service)
- `make clean` - Remove everything (DANGER!)

## Integration with Main Makefile

Already integrated! Use from the main directory:

```bash
make monitoring-start
make monitoring-stop
make monitoring-status
make monitoring-logs
```

## Python Client (for mercure-pediatric-leglength)

The `graphite_client.py` module can be used by mercure-pediatric-leglength to emit metrics to Graphite. See `DESIGN.md` for details.

## Design Philosophy

- **Lightweight**: No complex workflow tracking, just operational metrics
- **Standalone**: Independent from Orthanc, Mercure, and AI modules
- **Pre-configured**: Ready to read from Orthanc and Mercure out of the box
- **Simple**: Uses proven tools (Graphite, Prometheus, Grafana)
