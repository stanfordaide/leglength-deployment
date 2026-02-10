# Pediatric Leg Length AI - Deployment

Complete deployment package for the pediatric leg length measurement AI pipeline.

## Architecture Overview

```
                                    ┌─────────────────────────────┐
                                    │       MONITORING            │
                                    │  ┌─────────┐ ┌──────────┐  │
                                    │  │ Grafana │ │ Workflow │  │
                                    │  │         │ │    UI    │  │
                                    │  └────┬────┘ └────┬─────┘  │
                                    │       │          │         │
                                    │  ┌────┴──────────┴─────┐   │
                                    │  │     Prometheus      │   │
                                    │  │     Graphite        │   │
                                    │  └──────────┬──────────┘   │
                                    └─────────────┼──────────────┘
                                                  │
           ┌──────────────────────────────────────┼───────────────────────────────────┐
           │                                      │                                   │
           ▼                                      ▼                                   ▼
┌─────────────────────┐              ┌─────────────────────┐              ┌─────────────────────┐
│      ORTHANC        │              │      MERCURE        │              │    AI MODULE        │
│  ┌───────────────┐  │              │  ┌───────────────┐  │              │  ┌───────────────┐  │
│  │  DICOM Server │  │   DICOM      │  │  Dispatcher   │  │   Process    │  │  Leg Length   │  │
│  │               │──┼──────────────┼─▶│               │──┼──────────────┼─▶│   Detector    │  │
│  │  Lua Routing  │  │              │  │  Job Queue    │  │              │  │               │  │
│  │               │◀─┼──────────────┼──│               │◀─┼──────────────┼──│  PyTorch      │  │
│  └───────────────┘  │   Results    │  └───────────────┘  │   Results    │  └───────────────┘  │
│                     │              │                     │              │                     │
│  Port: 4242 (DICOM) │              │  Port: 8000 (Web)   │              │  (Docker container) │
│  Port: 8042 (Web)   │              │                     │              │                     │
└─────────────────────┘              └─────────────────────┘              └─────────────────────┘
```

## Components

| Directory | Description | README |
|-----------|-------------|--------|
| `orthanc/` | DICOM PACS server with intelligent routing | [→](orthanc/README.md) |
| `mercure/` | DICOM orchestration platform | [→](mercure/README.md) |
| `mercure-pediatric-leglength/` | AI processing module | [→](mercure-pediatric-leglength/README.md) |
| `monitoring/` | Grafana, Prometheus, workflow dashboard | [→](monitoring/README.md) |

## Quick Start

### Prerequisites

- Docker & Docker Compose
- 16GB+ RAM recommended
- GPU recommended for AI inference (but not required)

### 1. Setup Each Component

```bash
# Setup Orthanc (PACS)
cd orthanc
make setup
# Edit .env as needed
make start

# Setup Mercure (orchestrator)  
cd ../mercure
# Follow mercure setup instructions
docker compose -f docker/docker-compose.yml up -d

# Build AI module
cd ../mercure-pediatric-leglength
docker build -t mercure-pediatric-leglength:latest .
# Register in Mercure's module config

# Setup Monitoring
cd ../monitoring
make setup
# Edit .env to point to Orthanc/Mercure
make start
```

### 2. Configure Connections

#### Orthanc → Mercure
Edit `orthanc/config/orthanc.json` to add Mercure as a DICOM destination.

#### Orthanc → Monitoring
Configure Lua scripts to send events to monitoring API:
```lua
-- In orthanc/lua-scripts-v2/config.lua
CONFIG.TRACKING_API_URL = "http://<monitoring-host>:8044"
```

#### Mercure → Monitoring
Edit Mercure's `mercure.json`:
```json
{
  "graphite_ip": "<monitoring-host>",
  "graphite_port": 2003
}
```

## Data Flow

```
1. DICOM study arrives at Orthanc (port 4242)
          │
          ▼
2. Lua script analyzes study
   - Is it a bone length study?
   - Does it already have AI results?
          │
          ▼
3. Route to Mercure (if needs processing)
          │
          ▼
4. Mercure dispatches to AI module
          │
          ▼
5. AI module processes, returns results
          │
          ▼
6. Results sent back to Orthanc
          │
          ▼
7. Lua detects AI results, routes to final destination
```

## Ports Reference

| Service | Port | Protocol |
|---------|------|----------|
| **Orthanc** | | |
| DICOM | 4242 | DICOM |
| Web UI | 8042 | HTTP |
| **Mercure** | | |
| Web UI | 8000 | HTTP |
| **Monitoring** | | |
| Workflow UI | 8080 | HTTP |
| Workflow API | 8044 | HTTP |
| Grafana | 3000 | HTTP |
| Prometheus | 9090 | HTTP |
| Graphite | 2003 | Carbon |

## Development

Each component can be developed independently:

```bash
# Work on Orthanc Lua scripts
cd orthanc/lua-scripts-v2
# Changes are auto-loaded by Orthanc

# Work on AI module
cd mercure-pediatric-leglength
python run.py input/ output/  # Local testing

# Work on monitoring dashboard
cd monitoring/ui
# Edit index.html, refresh browser
```

## Troubleshooting

### Study not being routed
1. Check Orthanc logs: `cd orthanc && make logs`
2. Verify Lua scripts are loaded: Check for "Loaded lua-scripts-v2" in logs
3. Check matcher patterns in `orthanc/lua-scripts-v2/config.lua`

### AI processing failing
1. Check Mercure queue: Access Mercure Web UI
2. Check AI module logs: `docker logs mercure-processor`
3. Verify GPU access if using CUDA

### Monitoring not showing data
1. Check if routing-api is receiving events: `cd monitoring && make logs LOGS_SERVICE=workflow-api`
2. Verify Orthanc Lua is sending to correct URL
3. Check network connectivity between containers

## License

Internal use only - Stanford AIDE Lab
