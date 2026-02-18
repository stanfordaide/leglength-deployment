# Testing Monitoring Stack

## Quick Health Checks

### 1. Check Services Are Running
```bash
make monitoring-status
# OR
cd monitoring-v2 && docker compose ps
```

### 2. Test Grafana (should return 200)
```bash
curl -I http://localhost:9032/api/health
# Should see: HTTP/1.1 200 OK
```

### 3. Test Prometheus (should return 200)
```bash
curl -I http://localhost:9033/-/healthy
# Should see: HTTP/1.1 200 OK
```

### 4. Test Graphite (should return 200)
```bash
curl -I http://localhost:9041
# Should see: HTTP/1.1 200 OK
```

## Verify Data Collection

### 5. Check Prometheus is Scraping Orthanc
```bash
# Query Prometheus for Orthanc metrics
curl "http://localhost:9033/api/v1/query?query=orthanc_count_studies"

# Should return JSON with metric values
# If empty, check if Orthanc is accessible at host.docker.internal:9011
```

### 6. Check Orthanc Metrics Endpoint Directly
```bash
# From server, test if Orthanc exposes metrics
curl http://localhost:9011/tools/metrics-prometheus | head -20

# Should see metrics like:
# orthanc_count_studies 3 1771442681007
# orthanc_count_series 12 1771442681007
```

### 7. Test Graphite is Receiving Metrics
```bash
# Send a test metric to Graphite
echo "test.metric 42 $(date +%s)" | nc localhost 9038

# Query Graphite for the metric (wait a few seconds first)
curl "http://localhost:9041/render?target=test.metric&format=json&from=-1min"
```

### 8. Check Prometheus Targets
```bash
# View all scrape targets and their status
curl "http://localhost:9033/api/v1/targets" | jq '.data.activeTargets[] | {job: .labels.job, health: .health, lastError: .lastError}'

# Should show:
# - job: "prometheus" (self-monitoring)
# - job: "orthanc" (should be "up" if Orthanc is reachable)
```

## Verify Grafana Can Query Data

### 9. Login to Grafana
```bash
# Open in browser
http://localhost:9032

# Default credentials: admin/admin123 (or check config.env)
```

### 10. Test Prometheus Datasource in Grafana
1. Go to: Configuration → Data Sources → Prometheus
2. Click "Test" button
3. Should see: "Data source is working"

### 11. Test Graphite Datasource in Grafana
1. Go to: Configuration → Data Sources → Graphite
2. Click "Test" button
3. Should see: "Data source is working"

## Common Issues

### Prometheus Can't Reach Orthanc
```bash
# Check if host.docker.internal resolves correctly
docker exec prometheus ping -c 1 host.docker.internal

# If fails, check DOCKER_HOST_GATEWAY in config.env
# Linux: should be 172.17.0.1
# Mac/Windows: should be host.docker.internal
```

### No Orthanc Metrics in Prometheus
```bash
# Check Prometheus logs
docker logs prometheus | grep -i error

# Check if Orthanc metrics endpoint is accessible
docker exec prometheus wget -qO- http://host.docker.internal:9011/tools/metrics-prometheus | head -5
```

### Graphite Not Receiving Metrics
```bash
# Check Graphite logs
docker logs graphite | tail -20

# Test sending a metric manually
echo "test.manual 123 $(date +%s)" | nc localhost 9038
```

## Expected Results

✅ **All services healthy**: Grafana, Prometheus, Graphite return 200  
✅ **Prometheus scraping Orthanc**: `orthanc_count_studies` metric appears  
✅ **Grafana can query both**: Prometheus and Graphite datasources work  
✅ **No errors in logs**: `docker logs prometheus` and `docker logs graphite` show no errors
