# Pediatric Leg Length AI - Deployment

Complete deployment package for the pediatric leg length measurement AI pipeline.

## Architecture

```
┌─────────────────┐      ┌─────────────────┐      ┌─────────────────┐
│     ORTHANC     │      │     MERCURE     │      │   AI MODULE     │
│                 │      │                 │      │                 │
│  DICOM Server   │─────▶│  Job Queue      │─────▶│  Leg Length     │
│  Lua Routing    │◀─────│  Dispatcher     │◀─────│  Detector       │
│                 │      │                 │      │  (PyTorch)      │
└────────┬────────┘      └────────┬────────┘      └─────────────────┘
         │                        │
         │     Events/Metrics     │
         ▼                        ▼
┌─────────────────────────────────────────────────────────────────────┐
│                         MONITORING                                  │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐              │
│  │ Workflow UI  │  │   Grafana    │  │  Prometheus  │              │
│  │ (RADWATCH)   │  │  (metrics)   │  │  (collect)   │              │
│  └──────────────┘  └──────────────┘  └──────────────┘              │
└─────────────────────────────────────────────────────────────────────┘
```

## Components

| Directory | Description | README |
|-----------|-------------|--------|
| `orthanc/` | DICOM PACS server with Lua routing | [→](orthanc/README.md) |
| `mercure/` | DICOM orchestration platform | [→](mercure/README.md) |
| `mercure-pediatric-leglength/` | AI processing module (PyTorch) | [→](mercure-pediatric-leglength/README.md) |
| `monitoring/` | Grafana, Prometheus, workflow dashboard | [→](monitoring/README.md) |

## Prerequisites

- **OS**: RHEL 8/9 (for Mercure installer) or any Linux with Docker
- **Docker** & Docker Compose v2
- **RAM**: 16GB+ recommended
- **GPU**: Optional, improves AI inference speed

## Quick Start

### 1. Configure Everything (Once)

```bash
# Create master config file
make init

# Edit config.env with your passwords and settings
nano config.env

# Generate all component configs
make setup
```

This single `config.env` file controls ALL passwords, ports, and settings for every component.

### 2. Start Components (In Order)

```bash
# 1. Start Monitoring (event sink - must be first)
make monitoring-start

# 2. Start Orthanc (DICOM server)
cd orthanc && make setup && make start && cd ..

# 3. Install Mercure (uses password from config.env automatically)
make mercure-install

# 4. Build AI Module
make ai-build
```

### Access URLs

After setup, access services at (ports from your `config.env`):

| Service | Default URL |
|---------|-------------|
| Orthanc Operator UI | http://localhost:9010 |
| Orthanc Web/API | http://localhost:9011 |
| OHIF Viewer | http://localhost:9012 |
| Mercure Web UI | http://localhost:9020 |
| Workflow Dashboard | http://localhost:9030 |
| Grafana | http://localhost:9032 |
| DICOM Port | 4242 |

## Quick Commands

From the repository root:

```bash
# Status of all services
make status

# Start/stop all (after initial setup)
make start-all
make stop-all

# Individual components
make orthanc-start      make orthanc-stop      make orthanc-logs
make mercure-start      make mercure-stop      make mercure-logs
make monitoring-start   make monitoring-stop   make monitoring-logs

# Build AI module
make ai-build
```

## Data Flow

```
1. Study arrives at Orthanc (DICOM port 4242)
        │
        ▼
2. Lua script analyzes:
   - Is it a bone length study?
   - Does it already have AI results?
        │
        ▼
3. Routes to Mercure if needs AI processing
        │
        ▼
4. Mercure dispatches to AI module container
        │
        ▼
5. AI processes: detects landmarks, measures leg length
        │
        ▼
6. Results return to Orthanc as new DICOM series
        │
        ▼
7. Lua detects AI results → routes to final destination (PACS)
```

## Port Reference

All services use the **9000 series** for easy management:

| Component | Service | Port |
|-----------|---------|------|
| **Orthanc (9010s)** | Operator UI | 9010 |
| | Orthanc Web | 9011 |
| | OHIF Viewer | 9012 |
| | PostgreSQL | 9013 |
| | Routing API | 9014 |
| | DICOM | 4242 |
| **Mercure (9020s)** | Web UI | 9020 |
| | Bookkeeper | 9021 |
| | PostgreSQL | 9022 |
| **Monitoring (9030s)** | Workflow UI | 9030 |
| | Workflow API | 9031 |
| | **Grafana** | **9032** |
| | Prometheus | 9033 |
| | Alertmanager | 9034 |
| | Node Exporter | 9035 |
| | cAdvisor | 9036 |
| | Pushgateway | 9037 |
| | Graphite | 9038 |

> **Note:** All Grafana dashboards (Orthanc QI, Mercure, Infrastructure) are consolidated in the monitoring stack at port **9032**.

## Configuration

### Orthanc → Mercure Connection

Add Mercure as a DICOM modality in Orthanc:

```bash
cd orthanc
make seed-modalities    # Adds default destinations including MERCURE
```

### Orthanc → Monitoring Events

Edit `orthanc/lua-scripts-v2/config.lua`:

```lua
CONFIG.TRACKING_API_URL = "http://localhost:9031"
```

### Mercure → Graphite Metrics

Edit `/opt/mercure/config/mercure.json`:

```json
{
  "graphite_ip": "localhost",
  "graphite_port": 9038
}
```

## Key Files

| File | Purpose |
|------|---------|
| `orthanc/lua-scripts-v2/config.lua` | Routing rules, AI detection patterns |
| `orthanc/lua-scripts-v2/matcher.lua` | Study classification logic |
| `orthanc/lua-scripts-v2/router.lua` | Routing actions |
| `monitoring/api/app.py` | Workflow tracking API |
| `monitoring/ui/index.html` | RADWATCH dashboard |
| `mercure-pediatric-leglength/leglength/detector.py` | PyTorch model inference |

## Troubleshooting

### Study not being routed

1. Check Orthanc logs: `cd orthanc && make logs`
2. Verify Lua scripts loaded: Look for "Loaded lua-scripts-v2" in logs
3. Check matcher patterns in `orthanc/lua-scripts-v2/config.lua`

### AI processing failing

1. Check Mercure queue in Web UI
2. Check AI container logs: `docker logs <container-id>`
3. Verify GPU access if using CUDA

### Monitoring not receiving events

1. Check workflow-api logs: `cd monitoring && make logs LOGS_SERVICE=workflow-api`
2. Verify Orthanc Lua is POSTing to correct URL
3. Check network connectivity between containers

## Development

```bash
# Orthanc Lua scripts (auto-reload)
cd orthanc/lua-scripts-v2
# Edit files, Orthanc reloads automatically

# AI module (local testing)
cd mercure-pediatric-leglength
python run.py input/ output/

# Monitoring dashboard
cd monitoring/ui
# Edit index.html, refresh browser
```

## Security

### File Permissions
`make setup` automatically sets restrictive permissions (600) on all config files containing secrets:
- `config.env` - Master config
- `orthanc/.env` - Orthanc credentials
- `monitoring/.env` - Monitoring credentials
- `mercure/config-generated/*.env` - Mercure credentials

### Best Practices
- **Never commit** `config.env` or generated `.env` files (they're gitignored)
- **Generate strong passwords**: `openssl rand -base64 24`
- **Restrict server access** to trusted users only
- **For production**: Consider using Docker secrets or a secrets manager (HashiCorp Vault)

### What's Protected
| File | Permissions | Contains |
|------|-------------|----------|
| `config.env` | 600 | All passwords |
| `orthanc/.env` | 600 | Orthanc admin, DB passwords |
| `monitoring/.env` | 600 | Grafana, DB passwords |
| `mercure/config-generated/` | 600 | Mercure DB password |

## License

Internal use only - Stanford AIDE Lab
