# Pediatric Leg Length AI - Deployment

Complete deployment package for the pediatric leg length measurement AI pipeline.

## Quick Links

- **[CHANGES.md](CHANGES.md)** - Complete guide for making changes (configuration, make commands, workflows)
- **Component READMEs:** [`orthanc/`](orthanc/README.md) | [`mercure/`](mercure/README.md) | [`monitoring/`](monitoring/README.md)

## Architecture

```
┌──────────────────┐      ┌──────────────────┐      ┌──────────────────┐
│   ORTHANC PACS   │      │     MERCURE      │      │   AI MODULE      │
│  DICOM Server    │─────▶│  Job Dispatcher  │─────▶│  Leg Length      │
│  Lua Routing     │◀─────│  Bookkeeper DB   │◀─────│  Detector        │
└────────┬─────────┘      └────────┬─────────┘      └──────────────────┘
         │                         │
         └─────────────────────────┘
                    │
                    ▼
         ┌──────────────────────────┐
         │  MONITORING STACK        │
         │  ├─ Workflow UI          │
         │  ├─ Workflow API         │
         │  ├─ Grafana Dashboards   │
         │  └─ Prometheus Metrics   │
         └──────────────────────────┘
```

## Ports (9000 Series)

| Component | Service | Port |
|-----------|---------|------|
| **Orthanc** | Dashboard | 9010 |
| | Web/API | 9011 |
| | OHIF Viewer | 9012 |
| | PostgreSQL | 9013 |
| | DICOM | **4242** |
| **Mercure** | Web UI | 9020 |
| | PostgreSQL | 9022 |
| **Monitoring** | Workflow UI | 9030 |
| | Workflow API | 9031 |
| | Grafana | 9032 |
| | Prometheus | 9033 |

## Quick Start

### 1. Initialize Configuration

```bash
# Copy template and edit with your passwords
cp config.env.template config.env
vim config.env

# Generate component configs
sudo make setup
```

### 2. Start Services

```bash
# All services
sudo make start-all

# Or individually:
sudo make monitoring-start
sudo make orthanc-start
make mercure-install
make ai-build
```

### 3. Access Services

| Service | URL |
|---------|-----|
| Orthanc Web | http://localhost:9011 |
| OHIF Viewer | http://localhost:9012 |
| Workflow UI | http://localhost:9030 |
| Mercure | http://localhost:9020 |
| Grafana | http://localhost:9032 |

## Common Commands

```bash
# Status & Logs
make status                     # Show all services
make urls                       # Show service URLs
sudo make orthanc-logs          # Component logs
sudo make workflow-sync         # Recover workflow data

# Restart services
sudo make orthanc-restart       # Just Orthanc
sudo make monitoring-restart    # Just monitoring stack
sudo make restart-all           # Everything

# Debug
sudo make orthanc-debug         # Status + logs for one service
```

## Making Changes

**See [CHANGES.md](CHANGES.md) for complete guide:**

- How to edit `config.env.template` safely
- When to run `make setup`
- How to update code and restart services
- Troubleshooting and best practices

**Quick example:**

```bash
# 1. Edit configuration
vim config.env.template

# 2. Regenerate configs & restart
sudo make setup
sudo docker compose -f {stack}/docker-compose.yml restart {service}

# 3. Verify
sudo docker compose ps
```

## Data Flow

```
1. Study arrives at Orthanc (DICOM port 4242)
2. Lua script analyzes: needs AI processing?
3. If yes, routes to Mercure job queue
4. Mercure dispatches to AI module for processing
5. AI results returned to Orthanc
6. Lua routes final results to PACS destination
```

## Security

- `config.env` never checked in (in .gitignore)
- All config files: 600 permissions (owner only)
- Generate passwords: `openssl rand -base64 24`

## Directory Structure

```
leglength-deployment/
├── orthanc/               # DICOM PACS & Lua routing
├── mercure/               # Job orchestration  
├── monitoring/            # Workflow UI, API, Grafana
├── scripts/               # Setup & config generation
├── config.env.template    # Master configuration
├── CHANGES.md            # Change guide & best practices
└── Makefile              # Service orchestration
```

## License

Internal use only - Stanford AIDE Lab
