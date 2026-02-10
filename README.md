# Pediatric Leg Length AI - Deployment

Complete deployment package for the pediatric leg length measurement AI pipeline.

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
│  └──────────────┘  └──────────────┘  └──────────────┘              │
└─────────────────────────────────────────────────────────────────────┘
```

## Port Reference (9000 Series)

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

## Quick Start

### 1. Configure (One Time)

```bash
# Create master config
make init

# Edit with your passwords
nano config.env

# Generate all component configs
make setup
```

### 2. Start Components

```bash
# 1. Monitoring
make monitoring-start

# 2. Orthanc
cd orthanc
sudo make setup    # Creates directories (safe, never deletes data)
sudo make start
cd ..

# 3. Mercure
make mercure-install

# 4. AI Module
make ai-build
```

### 3. Access Services

| Service | URL |
|---------|-----|
| Orthanc Dashboard | http://localhost:9010 |
| Orthanc Web | http://localhost:9011 |
| OHIF Viewer | http://localhost:9012 |
| Mercure | http://localhost:9020 |
| Workflow UI | http://localhost:9030 |
| Grafana | http://localhost:9032 |

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

## Configuration

All settings are in one file: `config.env`

```bash
# Passwords
ORTHANC_ADMIN_PASS=...
MERCURE_DB_PASS=...
GRAFANA_PASS=...

# Storage paths
ORTHANC_DICOM_STORAGE=/home/data/orthanc-storage
ORTHANC_DB_STORAGE=/home/data/orthanc-pg

# Ports (defaults shown above)
```

Run `make setup` after editing to regenerate component configs.

## Data Flow

```
1. Study arrives → Orthanc (DICOM 4242)
2. Lua analyzes → needs AI? has AI results?
3. Route to Mercure → if needs processing
4. Mercure → AI module processes
5. Results back → Orthanc
6. Lua routes → final destination (PACS)
```

## Commands

```bash
# Status
make status

# Start/Stop all
make start-all
make stop-all

# Individual components
make monitoring-start    make monitoring-stop
make orthanc-start       make orthanc-stop
make mercure-start       make mercure-stop

# Logs
make monitoring-logs
cd orthanc && make logs
cd mercure && sudo /opt/mercure/mercure-manager.sh logs
```

## Troubleshooting

### Orthanc not starting
```bash
cd orthanc
make validate    # Check config
sudo make logs   # View logs
```

### Study not routing
1. Check Lua logs in Orthanc
2. Verify patterns in `orthanc/lua-scripts-v2/config.lua`

### AI processing failing
1. Check Mercure Web UI at :9020
2. View processor logs: `docker logs mercure_processor_1`

## Security

- All config files have 600 permissions (owner only)
- `config.env` is gitignored
- Generate strong passwords: `openssl rand -base64 24`

## License

Internal use only - Stanford AIDE Lab
