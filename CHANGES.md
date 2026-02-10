# Making Changes to the Deployment

This guide explains how to safely make changes to the system, keep configuration consistent, and use the deployment tools effectively.

## Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [Configuration Management](#configuration-management)
3. [Using Make Commands](#using-make-commands)
4. [Common Change Workflows](#common-change-workflows)
5. [Best Practices](#best-practices)
6. [Troubleshooting](#troubleshooting)

---

## Architecture Overview

The deployment is a **monorepo** with four main components:

```
leglength-deployment/
├── orthanc/              # DICOM PACS server
├── mercure/              # AI orchestration & job queue
├── monitoring/           # Workflow tracking UI & Analytics
│   ├── api/              # Flask backend (workflow-api)
│   └── ui/               # Vue.js frontend (workflow-ui)
└── config.env.template   # Master configuration (single source of truth)
```

**Communication Flow:**
- Orthanc receives DICOM studies → Routes via Lua scripts to Mercure
- Mercure manages AI job queue → Dispatches to AI module
- Monitoring tracks workflow state via Mercure Bookkeeper & Orthanc API
- UI displays real-time status and analytics

---

## Configuration Management

### The Single Source of Truth: `config.env.template`

All configuration lives in **`config.env.template`**. This ensures consistency across all services.

**Key variables:**

| Variable | Purpose | Example |
|----------|---------|---------|
| `ORTHANC_WEB_PORT` | Orthanc UI & API | `9011` |
| `MERCURE_BOOKKEEPER_PORT` | Mercure analytics DB | `9021` |
| `MONITORING_API_PORT` | Workflow API | `9031` |
| `MONITORING_UI_PORT` | Workflow UI | `9030` |
| `DOCKER_HOST_GATEWAY` | How containers reach host | `172.17.0.1` (Linux) or `host.docker.internal` (Mac) |
| `WORKFLOW_API_URL` | Orthanc calls this | `http://172.17.0.1:9031` |

### Propagating Changes

When you modify `config.env.template`, you **must run** `make setup` to propagate changes:

```bash
# 1. Edit config.env.template
# 2. Run setup to generate component-specific .env files
sudo make setup

# 3. Restart affected services
sudo docker compose -f monitoring/docker-compose.yml restart workflow-api
sudo docker compose -f orthanc/docker-compose.yml restart orthanc
```

**Why?** Each component reads from its own `.env` file (e.g., `monitoring/.env`, `orthanc/.env`) which are generated from the template via `scripts/setup-config.sh` using `envsubst`.

---

## Using Make Commands

The `Makefile` provides a consistent interface for all operations.

### Service Management

**Standard pattern:**
```bash
make {service}-{action}
```

**Available actions:**

| Action | Command | Purpose |
|--------|---------|---------|
| start | `sudo make orthanc-start` | Start container |
| stop | `sudo make orthanc-stop` | Stop container |
| restart | `sudo make orthanc-restart` | Restart container |
| status | `sudo make orthanc-status` | Show container status |
| logs | `sudo make orthanc-logs` | Show container logs |
| debug | `sudo make orthanc-debug` | Quick status + tail logs |

**Examples:**

```bash
# Start all services
sudo make start-all

# Restart a specific service
sudo make monitoring-restart

# View logs for workflow API
sudo make monitoring-logs

# Quick debug info
sudo make orthanc-debug
```

### AI Module Commands

```bash
make ai-build          # Build AI Docker image
make ai-test           # Run AI tests
make ai-clean          # Remove old images
make ai-push           # Push to registry
make ai-info           # Show image info
```

### Utilities

```bash
make help              # Show all commands
make urls              # Display all service URLs
make setup             # Generate configs from template
make workflow-sync     # Recover workflow state from Mercure
```

---

## Common Change Workflows

### Scenario 1: Change a Configuration Value

**Example:** Change Orthanc port from 9011 to 9012

```bash
# 1. Edit the template
vim config.env.template
# Change: ORTHANC_WEB_PORT=9012

# 2. Regenerate configs
sudo make setup

# 3. Restart the service
sudo docker compose -f orthanc/docker-compose.yml restart orthanc

# 4. Verify
make orthanc-status
curl http://localhost:9012/system
```

### Scenario 2: Update the Monitoring UI

**Example:** You modify `monitoring/ui/index.html` (like we just did)

```bash
# 1. Make your changes to monitoring/ui/index.html

# 2. Commit changes locally
git add monitoring/ui/index.html
git commit -m "UI: describe changes here"
git push origin main

# 3. On the server, pull and restart
cd /opt/projects/leglength-deployment
git pull origin main
sudo docker compose -f monitoring/docker-compose.yml restart workflow-ui

# 4. Verify UI loaded
curl http://localhost:9030
```

### Scenario 3: Update the Workflow API

**Example:** You modify `monitoring/api/app.py`

```bash
# 1. Make your changes

# 2. Rebuild the Docker image
sudo docker build -f monitoring/api/Dockerfile -t workflow-api:latest monitoring/api/

# 3. Restart the container
sudo docker compose -f monitoring/docker-compose.yml restart workflow-api

# 4. Check logs
make monitoring-logs
```

### Scenario 4: Recover Lost Workflow Data

**Example:** Monitoring database was reset, but studies are in Orthanc

```bash
# Sync from Mercure's Bookkeeper database
make workflow-sync

# Or manually:
curl -X POST http://localhost:9031/workflows/sync

# Check results
curl http://localhost:9031/workflows
```

---

## How Job Tracking Works (3 Stages)

The system uses **async job completion tracking** across the entire pipeline to get TRUE status:

### Stage 1: Send to MERCURE (AI Processing Initiation)

```
Orthanc              Workflow API         Orthanc
(Lua)                (Flask)              (Jobs)
  │                     │                    │
  │ SendToModality()    │                    │
  │─────────────────────┤ job_id returned    │
  │                     │                    │
  │ registerPendingJob()│                    │
  ├────────────────────>│ /track/job         │
  │  (MERCURE)          │                    │
  │                     │ Every 10s:         │
  │                     ├───────────────────>│
  │                     │ GET /jobs/{id}     │
  │                     │<───────────────────┤
  │                     │ State: Success     │
  │                     │ (Mercure got data) │
  │                     │                    │
  │                     │ UPDATE workflow:   │
  │                     │ mercure_sent = ✓   │
```

**Status field:** `mercure_sent_at`, `mercure_send_success`  
**True meaning:** Data successfully reached Mercure's incoming queue

### Stage 2: AI Processing Complete (Results Received)

```
Mercure               Orthanc              Workflow API
(AI Module)           (receives study)     (Flask)
  │                     │                    │
  │ Process...          │                    │
  │ Return results      │                    │
  │ as new study        │                    │
  │                     │ OnStableStudy()    │
  │                     │ (AI_RESULT study)  │
  │                     │                    │
  │                     │ Tracker.aiResultsReceived()
  │                     ├───────────────────>│
  │                     │ POST /track/ai-results
  │                     │                    │
  │                     │                    │ UPDATE workflow:
  │                     │                    │ ai_results_received = ✓
  │                     │                    │ ai_results_received_at = NOW()
```

**Status fields:** `ai_results_received`, `ai_results_received_at`  
**True meaning:** Processing completed and results returned to Orthanc

### Stage 3: Final Destinations (LPCH, LPCHT, MODLINK)

Same async job tracking as Stage 1:

**Status fields:** `lpch_sent_at`, `lpcht_sent_at`, `modlink_sent_at` + `_send_success`/`_send_error`  
**True meaning:** Data delivered to final PACS destinations

---

## Complete Pipeline Status Visualization

**UI displays all 3 stages in pipeline column:**

```
┌──────────────────────────────────────────────┐
│  MERCURE    →    AI    →    DESTINATIONS     │
│    ✓              ✓              ⚠            │
│  Sent     Processed    Partial Success       │
└──────────────────────────────────────────────┘
```

**Database schema** (study_workflows table):
- Stage 1: `mercure_sent_at`, `mercure_send_success`, `mercure_send_error`
- Stage 2: `ai_results_received_at`, `ai_results_received`
- Stage 3: `lpch_sent_at`, `lpcht_sent_at`, `modlink_sent_at` + success/error for each

**Monitoring in logs:**
```bash
# Watch job poller for MERCURE + destination jobs
sudo make monitoring-logs | grep "\[JobPoller\]"

# Example:
# [JobPoller] Checking 5 pending jobs...
# [JobPoller] ✓ Job abc123 SUCCEEDED (MERCURE) - AI queue received data
# [JobPoller] ✓ Job def456 SUCCEEDED (LPCHROUTER) - LPCH received results
# [JobPoller] ✗ Job ghi789 FAILED (MODLINK): Connection timeout
```

**How each stage gets marked complete:**

| Stage | Triggered By | Status Updated By |
|-------|--------------|-------------------|
| MERCURE | `routeToAI()` calls `SendToModality()` → registers job | Background poller checks `/jobs/{id}` every 10s |
| AI Results | AI returns study → `Tracker.aiResultsReceived()` | Explicit API call with timestamp |
| Destinations | `routeToFinalDestinations()` → registers job | Background poller checks `/jobs/{id}` every 10s |

---

## Best Practices

### 1. **Always Use `config.env.template` for Environment-Specific Settings**

❌ **Don't hardcode values** in Docker Compose files or code:
```yaml
environment:
  - ORTHANC_URL=http://localhost:9011
```

✅ **Do use template variables**:
```yaml
environment:
  - ORTHANC_URL=http://${DOCKER_HOST_GATEWAY}:${ORTHANC_WEB_PORT}
```

### 2. **Run `make setup` After Any `config.env.template` Changes**

Without this, individual service `.env` files won't be updated:
```bash
# Edit template
vim config.env.template

# Regenerate all service configs
sudo make setup

# Restart services that need new config
sudo make orthanc-restart
sudo make monitoring-restart
```

### 3. **Use Make Commands Instead of Direct Docker Commands**

✅ **Preferred:**
```bash
sudo make orthanc-logs
sudo make monitoring-restart
```

❌ **Avoid:**
```bash
sudo docker logs orthanc
sudo docker restart workflow-api
```

**Why?** The `Makefile` handles permissions (`sudo`), paths, and provides consistent naming.

### 4. **Test Changes Locally Before Pushing**

For UI/API changes:
```bash
# Test locally first
docker compose -f monitoring/docker-compose.yml up

# Then commit and push
git push origin main

# Then on server
cd /opt/projects/leglength-deployment
git pull origin main
sudo make monitoring-restart
```

### 5. **Always Check Status After Restarting**

```bash
# After any restart
make {service}-status
make {service}-logs

# Verify connectivity
curl http://localhost:{port}/health
```

### 6. **Document Your Changes**

Commit messages should be clear:

✅ **Good:**
```
Refactor UI: Consolidate pipeline chips into Recent Studies table

- Remove redundant 'Recent Studies Pipeline' section
- Move pipeline status into main table headers
- Add helper functions for workflow lookup
```

❌ **Vague:**
```
Update UI
```

---

## Troubleshooting

### Service Won't Start After Config Change

```bash
# 1. Check if config was properly applied
sudo cat orthanc/.env | grep ORTHANC_WEB_PORT

# 2. Regenerate config
sudo make setup

# 3. Restart service
sudo make {service}-restart

# 4. Check logs
sudo docker compose -f {stack}/docker-compose.yml logs {service}
```

### Configuration Changes Not Taking Effect

**Symptom:** Changed `config.env.template` but service still using old value

**Solution:**
```bash
# 1. Regenerate configs from template
sudo make setup

# 2. Verify the component's .env was updated
sudo cat monitoring/.env | grep WORKFLOW_API_PORT

# 3. Restart with new config
sudo docker compose -f monitoring/docker-compose.yml restart workflow-api
```

### Container Can't Reach Another Service

**Symptom:** Workflow API can't connect to Orthanc

**Diagnosis:**
```bash
# Check if DOCKER_HOST_GATEWAY is correct for your platform
cat config.env | grep DOCKER_HOST_GATEWAY
# Linux: Should be 172.17.0.1
# macOS/Docker Desktop: Should be host.docker.internal

# Test connectivity from inside container
sudo docker exec workflow-api curl http://172.17.0.1:9011/system
```

**Solution:** Update `config.env.template` with correct gateway, then `sudo make setup && sudo docker compose restart`

### Database Connection Errors

**Symptom:** `connection refused` in logs

```bash
# Check which database host/port is being used
sudo docker exec workflow-api env | grep DB

# Verify database is accessible
sudo docker exec workflow-api curl http://172.17.0.1:9022/
```

---

## Quick Reference

### Most Common Tasks

```bash
# Pull latest changes and update config
git pull origin main
sudo make setup

# Restart all services
sudo make restart-all

# Check everything is running
make status

# View service URLs
make urls

# Read logs for debugging
sudo make monitoring-logs
sudo make orthanc-logs

# Recover workflow data
make workflow-sync
```

### File Locations (Local Development)

- **Main config:** `/dataNAS/people/arogya/projects/leglength-deployment/config.env.template`
- **Generated configs:** `{component}/.env` (auto-generated by `make setup`)
- **Docker Compose files:** `{component}/docker-compose.yml`
- **Setup script:** `scripts/setup-config.sh`

### File Locations (Server `/opt`)

```
/opt/projects/leglength-deployment/
├── config.env (from config.env.template)
├── orthanc/.env (from setup-config.sh)
├── mercure/.env
├── monitoring/.env
└── [docker-compose files]
```

---

## Summary

**To make changes safely:**

1. **Identify what's changing:** Config? Code? UI?
2. **Edit appropriately:**
   - Config values → `config.env.template`
   - UI → `monitoring/ui/`
   - API logic → `monitoring/api/app.py`
   - Docker setup → `{component}/docker-compose.yml`
3. **Propagate changes:**
   - Run `sudo make setup` if config changed
   - Rebuild/restart affected services
4. **Verify:**
   - Check status: `make {service}-status`
   - Check logs: `make {service}-logs`
   - Test manually: `curl` / browser
5. **Commit & push when working:**
   - `git add -A && git commit && git push`
6. **On server:**
   - `git pull origin main`
   - `sudo make setup` (if needed)
   - `sudo docker compose restart` (if needed)
