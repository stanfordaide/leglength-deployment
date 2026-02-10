# Project Context - Pediatric Leg Length AI Deployment

> This file captures the conversation context for continuing development in a new Cursor window.

## What This Project Is

A **monorepo** consolidating 4 components of the pediatric leg length AI pipeline:

```
leglength-deployment/
├── orthanc/                    # DICOM PACS server (from ../orthanc)
├── mercure/                    # AI orchestration platform (from ../mercure)
├── mercure-pediatric-leglength/  # AI processing module
└── monitoring/                 # NEW: Unified dashboards & workflow tracking
```

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

## Data Flow

1. **Study arrives** at Orthanc (DICOM port 4242)
2. **Lua script analyzes** - Is it bone length? Has AI results?
3. **Routes to Mercure** if needs AI processing
4. **Mercure dispatches** to `mercure-pediatric-leglength` container
5. **AI processes** - detects landmarks, measures leg length
6. **Results return** to Orthanc as new DICOM series
7. **Lua detects AI results** - routes to final destination (PACS)

## Key Design Decisions Made

### 1. Lua Routing Logic (`orthanc/lua-scripts-v2/`)
- **Modular design**: `main.lua`, `config.lua`, `matcher.lua`, `router.lua`, `tracker.lua`
- **AI result detection**: Checks `Manufacturer=STANFORDAIDE`, `SeriesDescription` patterns
- **Prevents loops**: Won't re-send studies that already have AI output
- **Fresh reprocess**: `clearAIOutput()` + `resetTracking()` + re-route

### 2. Workflow Tracking (`monitoring/api/`)
- Flask API receives events from Lua scripts
- Stores in PostgreSQL: study arrivals, Mercure sends, AI results, final routes
- Provides funnel visualization data

### 3. Monitoring Stack (`monitoring/`)
- **Workflow UI** (port 9080): Vue.js dashboard for study tracking + actions
- **Grafana** (port 9000): Infrastructure metrics, disk, containers
- **Prometheus** (port 9090): Metrics collection
- **Graphite** (port 2003): Mercure native metrics

## Port Assignments (9000 Series)

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
| | **Grafana (unified)** | **9032** |
| | Prometheus | 9033 |
| | Alertmanager | 9034 |
| | Graphite | 9038 |

> All Grafana dashboards consolidated in monitoring stack (port 9032)

## Credentials

### Orthanc
- Web UI: `orthanc_admin` / `helloaide123`
- PostgreSQL: `orthanc` / `orthanc123`

### Mercure DB
- Host: `mercure_db_1`
- User: `mercure`
- Pass: `GOLtgqwpBUF9n23gQpORcPVJsO4r4lRj`

### Monitoring
- Grafana: `admin` / `admin123`
- Workflow DB: `workflow` / `workflow123`

## Recent Fixes Applied

### 1. PyTorch UID Issue (mercure-pediatric-leglength)
- **Problem**: `KeyError: 'getpwuid(): uid not found: 1001'`
- **Fix**: Added `TORCHINDUCTOR_CACHE_DIR=/tmp/torch_inductor_cache` and `HOME=/app/v0` to Dockerfile
- **Also**: Added `fix_passwd_entry()` in `docker_entrypoint.sh`

### 2. AI Result Detection (orthanc/lua-scripts-v2/)
- **Problem**: Studies with AI results were being re-sent to Mercure
- **Fix**: Updated `config.lua` patterns: `STANFORDAIDE`, `QA VISUALIZATION`, `AI MEASUREMENTS`, `SR`
- **Also**: Added safety check in `matcher.lua` - if AI output exists, return `UNMATCHED`

### 3. Workflow API JSON Parsing
- **Problem**: Lua was sending malformed JSON
- **Fix**: Changed `JsonEncode` to `DumpJson`, fixed HTTP headers

## Commands

```bash
# From leglength-deployment/

# Status
make status

# Start/Stop
make start-all
make stop-all

# Individual components
make orthanc-start
make mercure-start  
make monitoring-start
make ai-build

# Logs
make orthanc-logs
make monitoring-logs
```

## Next Steps / TODOs

1. **Configure Orthanc → Monitoring connection**
   - Update Lua scripts to POST events to `http://<monitoring>:9044/track/*`

2. **Configure Mercure → Graphite**
   - Edit `mercure/mercure.json` to set `graphite_ip` and `graphite_port`

3. **Create Grafana dashboards**
   - Disk usage for Orthanc storage
   - Mercure queue depths
   - AI processing times

4. **Test end-to-end flow**
   - Upload study → Orthanc → Mercure → AI → Results back → Final route

5. **Add alerting**
   - Disk space warnings
   - Failed jobs in Mercure
   - Studies stuck > 1 hour

## Files to Know

| File | Purpose |
|------|---------|
| `orthanc/lua-scripts-v2/config.lua` | Routing rules, AI detection patterns |
| `orthanc/lua-scripts-v2/matcher.lua` | Study classification logic |
| `orthanc/lua-scripts-v2/router.lua` | Routing actions, clearAIOutput |
| `monitoring/api/app.py` | Workflow tracking API |
| `monitoring/ui/index.html` | RADWATCH dashboard |
| `mercure-pediatric-leglength/Dockerfile` | AI module container |
| `mercure-pediatric-leglength/leglength/detector.py` | PyTorch model inference |

---

*Generated: 2026-02-09*
