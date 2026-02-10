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

## Setup Order

Components should be started in this order due to dependencies:

```
1. Monitoring  →  2. Orthanc  →  3. Mercure  →  4. AI Module
```

### 1. Monitoring (Event Sink)

```bash
cd monitoring
make setup          # Creates .env and data directories
# Edit .env if needed
make start
```

**Access:**
- Workflow UI: http://localhost:9030
- Workflow API: http://localhost:9031
- Grafana: http://localhost:9032 (`admin` / `admin123`)
- Prometheus: http://localhost:9033

### 2. Orthanc (DICOM Server)

```bash
cd orthanc
make menu           # Interactive setup wizard (recommended)
# OR for scripted setup:
make setup DICOM_STORAGE=/path/to/dicom POSTGRES_STORAGE=/path/to/db
make start
```

**Access:**
- Operator Dashboard: http://localhost:9010
- Orthanc Web UI: http://localhost:9011 (`orthanc_admin` / `helloaide123`)
- OHIF Viewer: http://localhost:9012
- DICOM Port: 4242

### 3. Mercure (Job Dispatcher)

```bash
cd mercure
sudo ./install_rhel_v2.sh -y    # Full installation

# After install, services are at /opt/mercure
# Manage with:
sudo /opt/mercure/mercure-manager.sh status
sudo /opt/mercure/mercure-manager.sh start
sudo /opt/mercure/mercure-manager.sh stop
```

**Access:**
- Mercure Web UI: http://localhost:8000

### 4. AI Module (Docker Image)

```bash
# From repo root
make ai-build       # Builds mercure-pediatric-leglength:latest
```

The AI module runs as a Docker container managed by Mercure. Register it in Mercure's module configuration.

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

## License

Internal use only - Stanford AIDE Lab
