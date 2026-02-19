# Network Architecture Proposal

## Current State

### Ports Currently Exposed to Host

| Port | Service | Purpose | External Access Needed? |
|------|---------|---------|------------------------|
| **4242** | Orthanc DICOM | C-STORE from external modalities | ✅ YES (DICOM) |
| **9010** | Orthanc Web/API | Web UI, API access | ✅ YES (Browser/API) |
| **9012** | OHIF Viewer | Clinical image viewer | ✅ YES (Browser) |
| **9013** | Orthanc PostgreSQL | Database | ❌ NO (internal only) |
| **9020** | Mercure UI | Job management UI | ✅ YES (Browser) |
| **9022** | Mercure PostgreSQL | Database | ❌ NO (internal only) |
| **11112** | Mercure DICOM Receiver | Receive DICOM from Orthanc | ⚠️ MAYBE (if external) |
| **9030** | Grafana | Metrics dashboard | ✅ YES (Browser) |
| **9031** | Workflow API | API for workflow tracking | ❌ NO (internal only) |
| **9033** | Prometheus | Metrics query API | ⚠️ MAYBE (debugging) |
| **9034** | Alertmanager | Alert management | ❌ NO (internal) |
| **9038** | Graphite Carbon | Metrics ingestion | ⚠️ MAYBE (if external) |
| **9039** | Graphite Pickle | Metrics ingestion | ⚠️ MAYBE (if external) |
| **9041** | Graphite Web | Graphite UI | ❌ NO (use Grafana) |
| **9042** | Monitoring PostgreSQL | Database | ❌ NO (internal only) |

### Current Network Configuration

- **Orthanc**: Default bridge network (isolated)
- **Mercure**: `mercure_default` network (isolated)
- **Monitoring**: `monitoring-net` network (isolated)
- **Communication**: Via host gateway (172.17.0.1) - not ideal

## Proposed Architecture: Single Shared Network

### Benefits

1. **Service Discovery**: Containers can communicate by service name
2. **No Host Gateway**: Direct container-to-container communication
3. **Simplified Configuration**: No need for IP addresses
4. **Better Security**: Internal services not exposed to host
5. **Easier Debugging**: All containers visible to each other

### Implementation

#### 1. Create External Shared Network

```yaml
# Create once: docker network create leglength-network
```

#### 2. Network Configuration

**External Network**: `leglength-network` (created externally, shared by all stacks)

**Port Exposure Strategy**:
- **Expose to Host**: Only services that need external access
- **Internal Only**: Databases, internal APIs, workers

#### 3. Recommended Port Exposure

**Expose to Host** (External Access):
- `4242` - Orthanc DICOM (required for external modalities)
- `9010` - Orthanc Web/API (browser access)
- `9012` - OHIF Viewer (browser access)
- `9020` - Mercure UI (browser access)
- `9030` - Grafana (browser access)
- `11112` - Mercure DICOM Receiver (if receiving from external)

**Internal Only** (No Host Exposure):
- All PostgreSQL databases (9013, 9022, 9042)
- Workflow API (9031) - accessed via service name
- Prometheus (9033) - accessed via Grafana
- Graphite (9038, 9039, 9041) - accessed via service name
- Redis, workers, processors - all internal

### Service Communication Examples

With shared network, containers communicate like this:

```bash
# Orthanc → Workflow API (instead of http://172.17.0.1:9031)
WORKFLOW_API_URL=http://workflow-api:9031

# Grafana → Prometheus (instead of http://prometheus:9090)
# Already configured correctly

# Grafana → Monitoring PostgreSQL (instead of postgres:5432)
# Already configured correctly

# Mercure → Graphite (instead of 172.17.0.1:9038)
graphite_ip: graphite
graphite_port: 2003  # Internal port, not host port

# Orthanc → Mercure (DICOM)
# Use service name: mercure-receiver:11112
```

## Migration Plan

### Step 1: Create External Network

```bash
docker network create leglength-network
```

### Step 2: Update docker-compose Files

1. **Orthanc**: Join `leglength-network`, remove host gateway references
2. **Mercure**: Join `leglength-network`, update service names
3. **Monitoring**: Join `leglength-network`, already mostly correct

### Step 3: Update Configuration

- Remove `DOCKER_HOST_GATEWAY` dependencies
- Update service URLs to use service names
- Remove unnecessary port exposures

### Step 4: Update Environment Variables

- `WORKFLOW_API_URL`: `http://workflow-api:9031` (instead of `http://172.17.0.1:9031`)
- Graphite IP: `graphite` (instead of `172.17.0.1`)
- Database connections: Use service names

## Port Summary

### Exposed to Host (External Access)
```
4242  - Orthanc DICOM
9010  - Orthanc Web/API
9012  - OHIF Viewer
9020  - Mercure UI
9030  - Grafana
11112 - Mercure DICOM Receiver (if needed)
```

### Internal Only (Service Name Access)
```
All databases (9013, 9022, 9042)
Workflow API (9031)
Prometheus (9033)
Graphite (9038, 9039, 9041)
Alertmanager (9034)
All workers, processors, etc.
```

## Security Considerations

1. **Database Ports**: Not exposed - only accessible from containers on the network
2. **Internal APIs**: Not exposed - only accessible via service names
3. **DICOM Ports**: Exposed only if needed for external modalities
4. **Network Isolation**: All containers isolated from host except exposed ports

## Next Steps

1. Review and approve this architecture
2. Create migration script to update all docker-compose files
3. Update configuration files to use service names
4. Test inter-container communication
5. Remove host gateway dependencies
