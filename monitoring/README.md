# Leg Length AI Deployment - Monitoring Stack

Consolidated monitoring and control center for the pediatric leg length AI pipeline.

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                     leglength-deployment                                    │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                        Visualization                                │   │
│  │  ┌─────────────────┐           ┌─────────────────┐                 │   │
│  │  │  Workflow UI    │           │     Grafana     │                 │   │
│  │  │  (Vue.js)       │           │                 │                 │   │
│  │  │  :8080          │           │  :3000          │                 │   │
│  │  │                 │           │                 │                 │   │
│  │  │  • Study list   │◀─────────▶│  • Disk usage   │                 │   │
│  │  │  • Actions      │   links   │  • Containers   │                 │   │
│  │  │  • OHIF viewer  │           │  • Alerts       │                 │   │
│  │  └────────┬────────┘           └────────┬────────┘                 │   │
│  └───────────┼─────────────────────────────┼───────────────────────────┘   │
│              │                             │                               │
│              ▼                             ▼                               │
│  ┌─────────────────┐   ┌─────────────────┐   ┌─────────────────┐          │
│  │  Workflow API   │   │   Prometheus    │   │    Graphite     │          │
│  │  (Flask)        │   │   (metrics)     │   │  (Mercure)      │          │
│  │  :8044          │   │   :9090         │   │  :2003          │          │
│  └────────┬────────┘   └────────┬────────┘   └────────┬────────┘          │
│           │                     │                     │                   │
│           ▼                     │                     │                   │
│  ┌─────────────────┐            │                     │                   │
│  │  PostgreSQL     │            │                     │                   │
│  │  (workflow DB)  │            │                     │                   │
│  └─────────────────┘            │                     │                   │
└─────────────────────────────────┼─────────────────────┼───────────────────┘
                                  │                     │
         ┌────────────────────────┼─────────────────────┼────────────────┐
         │                        │                     │                │
         ▼                        ▼                     ▼                ▼
    ┌─────────┐              ┌─────────┐          ┌─────────┐      ┌─────────┐
    │ Orthanc │              │ Docker  │          │ Mercure │      │  Host   │
    │  PACS   │              │ cAdvisor│          │         │      │  Node   │
    └─────────┘              └─────────┘          └─────────┘      └─────────┘
```

## Services

| Service | Port | Description |
|---------|------|-------------|
| **workflow-ui** | 8080 | Study tracking dashboard with action buttons |
| **workflow-api** | 8044 | REST API for workflow events and actions |
| **grafana** | 3000 | Infrastructure dashboards and alerting |
| **prometheus** | 9090 | Metrics collection and storage |
| **graphite** | 2003 | Mercure metrics receiver |
| **node-exporter** | 9100 | Host system metrics |
| **cadvisor** | 8081 | Docker container metrics |
| **alertmanager** | 9093 | Alert routing and notifications |

## Quick Start

```bash
# 1. Copy environment template
cp env.template .env

# 2. Edit configuration
vim .env

# 3. Start the stack
docker compose up -d

# 4. Access dashboards
#    - Workflow UI: http://localhost:8080
#    - Grafana: http://localhost:3000
```

## Configuration

### Connecting to Orthanc

The workflow API can send actions to Orthanc. Configure in `.env`:

```bash
ORTHANC_URL=http://host.docker.internal:8042
ORTHANC_USER=orthanc
ORTHANC_PASS=orthanc
```

### Connecting to Mercure

For enriched job tracking, connect to Mercure's database:

```bash
MERCURE_DB_HOST=mercure_db_1
MERCURE_DB_PORT=5432
MERCURE_DB_NAME=mercure
MERCURE_DB_USER=mercure
MERCURE_DB_PASS=your_password
```

### Mercure → Graphite

Configure Mercure to send metrics to this stack. In `mercure.json`:

```json
{
  "graphite_ip": "localhost",
  "graphite_port": 2003
}
```

## Orthanc Integration

For Orthanc to send workflow events to this stack, configure the Lua scripts to POST to:

```
http://<this-host>:8044/track/start
http://<this-host>:8044/track/mercure-sent
http://<this-host>:8044/track/ai-results
http://<this-host>:8044/track/final-route
```

## Actions Available

The workflow UI provides these actions:

| Action | Description |
|--------|-------------|
| **Re-route to Mercure** | Send a study back through AI processing |
| **Clear AI Output** | Remove AI-generated series from a study |
| **Fresh Reprocess** | Clear + reset tracking + re-route |
| **View in OHIF** | Open study in DICOM viewer |

## Alerts

Pre-configured alerts:

- **DiskSpaceWarning** - Disk below 20% free
- **DiskSpaceCritical** - Disk below 10% free
- **ContainerDown** - Critical container stopped
- **ContainerRestarting** - Frequent restarts detected
- **NoStudiesReceived** - No new studies in 24h

Configure Slack notifications in `.env`:

```bash
SLACK_WEBHOOK_URL=https://hooks.slack.com/services/...
SLACK_CHANNEL=#alerts
```

## Directory Structure

```
leglength-deployment/
├── docker-compose.yml      # Main orchestration
├── env.template            # Configuration template
├── api/
│   ├── Dockerfile
│   ├── app.py              # Workflow tracking API
│   └── requirements.txt
├── ui/
│   └── index.html          # Workflow dashboard
├── config/
│   ├── nginx/
│   │   └── default.conf    # UI server config
│   ├── prometheus/
│   │   ├── prometheus.yml  # Scrape targets
│   │   ├── alert_rules.yml # Alert definitions
│   │   └── alertmanager.yml
│   └── grafana/
│       ├── provisioning/
│       │   └── datasources/
│       └── dashboards/
└── scripts/
    └── (utility scripts)
```

## Related Projects

- `orthanc/` - DICOM PACS server
- `mercure/` - AI orchestration platform
- `mercure-pediatric-leglength/` - AI processing module
