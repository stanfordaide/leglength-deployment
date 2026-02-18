# Monitoring - Design

**Philosophy**: Keep it simple. Use Graphite for time-series metrics (like Mercure), Grafana for visualization, and operational metrics only.

## Architecture

```
┌─────────────────┐         ┌──────────┐         ┌─────────┐
│  mercure-ped    │────────▶│ Graphite │◀────────│ Grafana │
│  -leglength     │         │          │         │         │
└─────────────────┘         └──────────┘         └─────────┘
                                      ▲
┌─────────────────┐                   │
│    Orthanc      │───────────────────┘
│  (Prometheus)   │  (scraped by Prometheus → Graphite)
└─────────────────┘
```

## Components

### 1. Graphite (Time-Series Storage)
- **Already running** on port 9038
- Receives metrics via Carbon line protocol (port 2003)
- Simple format: `metric.name value timestamp`

### 2. Grafana (Visualization)
- **Already running** on port 9032
- **Already configured** with Graphite datasource
- Create dashboards for operational metrics

### 3. Prometheus (Optional - for Orthanc)
- Keep for scraping Orthanc's built-in `/tools/metrics-prometheus`
- Can forward to Graphite if needed (via prometheus-to-graphite bridge)

## Metrics to Emit

### From mercure-pediatric-leglength

**Format**: `leglength.{metric_name} {value} {timestamp}`

**Metrics**:
```
leglength.inference.started          # Counter: AI inference started
leglength.inference.completed        # Counter: AI inference completed  
leglength.inference.failed           # Counter: AI inference failed
leglength.inference.duration_ms      # Timer: Processing time in milliseconds
leglength.measurements.femur_cm      # Gauge: Femur measurement
leglength.measurements.tibia_cm      # Gauge: Tibia measurement
leglength.measurements.total_cm      # Gauge: Total leg length
leglength.models.{model_name}.used   # Counter: Model usage count
```

### From Orthanc (via Prometheus)

**Already available**:
```
orthanc_count_studies
orthanc_count_series
orthanc_jobs_completed
orthanc_jobs_failed
```

**Custom metrics** (if needed, via Lua):
```
orthanc.routing.sent.{destination}   # Counter: Studies sent to destination
orthanc.routing.failed.{destination} # Counter: Failed sends
orthanc.ai_results.received          # Counter: AI results received
```

## Implementation

### mercure-pediatric-leglength → Graphite

**Library**: `graphyte` (same as Mercure uses)

**Simple wrapper**:
```python
# monitoring/graphite_client.py
import graphyte
import os

class GraphiteClient:
    def __init__(self, prefix="leglength"):
        host = os.getenv("GRAPHITE_HOST", "172.17.0.1")
        port = int(os.getenv("GRAPHITE_PORT", "9038"))
        self.prefix = prefix
        graphyte.init(host, port=port, prefix=prefix)
    
    def send(self, metric, value):
        graphyte.send(metric, value)
```

**Usage in run.py**:
```python
from monitoring import GraphiteClient

graphite = GraphiteClient()
graphite.send("inference.started", 1)
graphite.send("inference.duration_ms", processing_time * 1000)
```

### Orthanc → Prometheus (already working)

- Orthanc exposes `/tools/metrics-prometheus`
- Prometheus scrapes it (already configured)
- Grafana can query Prometheus directly

## Grafana Dashboards

**Simple operational dashboards**:

1. **AI Processing**
   - Inference rate (per hour)
   - Success/failure rate
   - Average processing time
   - Model usage distribution

2. **Orthanc Operations**
   - Studies received
   - Jobs completed/failed
   - Storage usage

3. **System Health**
   - Disk space (from node-exporter)
   - CPU/Memory (from cadvisor)
   - Service uptime

## What We DON'T Need

❌ Complex workflow tracking API  
❌ PostgreSQL workflow database  
❌ HTTP calls between services  
❌ Job polling  
❌ Workflow state reconstruction  

**Why?** These are operational metrics, not workflow state. If you need workflow tracking, use Mercure's Bookkeeper (PostgreSQL) for detailed analytics.

## Migration Path

1. ✅ Graphite already running
2. ✅ Grafana already configured
3. ✅ Prometheus already scraping Orthanc
4. ⏳ Add Graphite client to mercure-pediatric-leglength
5. ⏳ Create Grafana dashboards
6. ⏳ (Optional) Deprecate monitoring API

## Benefits

- **Simple**: Just emit metrics, no complex state management
- **Lightweight**: Graphite is much lighter than Prometheus + PostgreSQL
- **Proven**: Same approach Mercure uses successfully
- **Flexible**: Grafana can query both Graphite and Prometheus
- **No coupling**: Services don't need to know about each other
