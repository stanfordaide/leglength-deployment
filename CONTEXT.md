# Project Context - Pediatric Leg Length AI Deployment

> This file captures the conversation context for continuing development in a new Cursor window.

## What This Project Is

A **monorepo** consolidating 4 components of the pediatric leg length AI pipeline:

```
leglength-deployment/
├── orthanc/                    # DICOM PACS server (dumb pipe)
├── mercure/                    # AI orchestration platform
├── mercure-pediatric-leglength/  # AI processing module
└── monitoring/                 # Unified dashboards, metrics, workflow tracking
```

## Architecture

```
┌─────────────────┐      ┌─────────────────┐      ┌─────────────────┐
│     ORTHANC     │      │     MERCURE     │      │   AI MODULE     │
│                 │      │                 │      │                 │
│  DICOM Server   │─────▶│  Job Queue      │─────▶│  Leg Length     │
│  Lua Routing    │◀─────│  Dispatcher     │◀─────│  Detector       │
│   (dumb pipe)   │      │                 │      │  (PyTorch)      │
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

**Key Design**: Orthanc is a "dumb pipe" - receives DICOM, routes via Lua rules. No direct integration with Mercure databases. Monitoring stack handles all job tracking via Grafana's PostgreSQL datasources.

## Port Assignments (9000 Series)

| Component | Service | Port |
|-----------|---------|------|
| **Orthanc** | Operator Dashboard | 9010 |
| | Orthanc Web/API | 9011 |
| | OHIF Viewer | 9012 |
| | PostgreSQL | 9013 |
| | Routing API | 9014 |
| | **DICOM** | **4242** |
| **Mercure** | Web UI | 9020 |
| | Bookkeeper | 9021 |
| | PostgreSQL | 9022 |
| **Monitoring** | Workflow UI | 9030 |
| | Workflow API | 9031 |
| | Grafana | 9032 |
| | Prometheus | 9033 |
| | Alertmanager | 9034 |
| | Node Exporter | 9035 |
| | cAdvisor | 9036 |
| | Pushgateway | 9037 |
| | Graphite | 9038 |

## Data Flow

1. **Study arrives** at Orthanc (DICOM port 4242)
2. **Lua script analyzes** - Is it bone length? Has AI results?
3. **Routes to Mercure** if needs AI processing
4. **Mercure dispatches** to `mercure-pediatric-leglength` container
5. **AI processes** - detects landmarks, measures leg length
6. **Results return** to Orthanc as new DICOM series
7. **Lua detects AI results** - routes to final destination (PACS)

## Configuration

### Single Source of Truth: `config.env`

```bash
make init      # Create config.env from template
nano config.env  # Set passwords, paths, ports
make setup     # Generate component-specific configs
```

All credentials configured in one place, propagated to:
- `orthanc/.env`
- `monitoring/.env`
- Mercure installer

### Security
- All generated `.env` files have `chmod 600`
- `config.env` is gitignored
- No secrets in git history

## Credentials (defaults in config.env.template)

| Service | Username | Password Variable |
|---------|----------|-------------------|
| Orthanc Web | orthanc_admin | ORTHANC_ADMIN_PASS |
| Orthanc PostgreSQL | orthanc | ORTHANC_DB_PASS |
| Mercure PostgreSQL | mercure | MERCURE_DB_PASS |
| Grafana | admin | GRAFANA_PASS |
| Workflow DB | workflow | WORKFLOW_DB_PASS |

## Commands

```bash
# Setup (one time)
make init
make setup

# Start/Stop
make start-all
make stop-all

# Individual components
make monitoring-start    make monitoring-stop
make orthanc-start       make orthanc-stop
make mercure-start       make mercure-stop

# Status
make status
```

## Key Files

| File | Purpose |
|------|---------|
| `config.env` | Master configuration (not in git) |
| `scripts/setup-config.sh` | Generates component .env files |
| `orthanc/lua-scripts-v2/config.lua` | Routing rules, AI detection patterns |
| `monitoring/config/grafana/provisioning/` | Datasources, dashboards |
| `mercure-pediatric-leglength/Dockerfile` | AI module container |

## SSH Tunnel (Remote Access)

```bash
ssh -L 9010:192.168.56.105:9010 \
    -L 9011:192.168.56.105:9011 \
    -L 9012:192.168.56.105:9012 \
    -L 9020:192.168.56.105:9020 \
    -L 9030:192.168.56.105:9030 \
    -L 9032:192.168.56.105:9032 \
    -L 4242:192.168.56.105:4242 \
    -N user@jumphost
```

---

*Generated: 2026-02-09*
