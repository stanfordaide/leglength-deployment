# Installation Guide

Complete installation and maintenance guide for the Pediatric Leg Length AI deployment.

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Fresh Install](#1-fresh-install)
3. [Fresh Install After Clearing Everything](#2-fresh-install-after-clearing-everything)
4. [Updates](#3-updates)
5. [Debugging Workflow](#4-debugging-workflow)

---

## Quick Start (All Make Commands)

**Everything is automated via `make` commands!** Only 3 manual steps:

1. **Clone repository** (one-time, manual)
2. **Edit `config.env`** (set passwords/paths, manual)
3. **Browser login** (initial setup, manual)

**Everything else is automated:**

```bash
# Fresh Install
make init              # Create config.env from template
nano config.env        # Edit passwords/paths (manual)
make setup             # Generate all configs, install Mercure, create network
make ai-build          # Build AI Docker image
make start-all         # Start all services
make verify            # Verify all services are healthy

# Updates
git pull               # Pull latest code
make setup             # Regenerate configs
make ai-build          # Rebuild if code changed
make restart-all       # Restart services
make verify            # Verify health

# Clear Everything
make stop-all          # Stop all services
make clean-all         # Remove everything (with confirmation)
# Then follow Fresh Install from 'make init'

# Individual Service Reset
make <service>-stop    # Stop service
make <service>-clear   # Clear data (with confirmation)
make setup             # Regenerate configs
make <service>-start   # Start fresh
```

---

## Prerequisites

### System Requirements

| Requirement | Minimum Version | Check Command |
|-------------|----------------|---------------|
| **Docker** | 20.10+ | `docker --version` |
| **Docker Compose** | 2.0+ (V2) | `docker compose version` |
| **Python** | 3.10+ | `python3 --version` |
| **Git** | 2.0+ | `git --version` |
| **curl** | any | `curl --version` |

**Hardware:**
- RAM: 4GB minimum, 8GB recommended
- Disk: 50GB minimum for system, plus storage for DICOM data
- Ports: See [Port Assignments](#port-assignments) below

### Port Assignments

**Exposed to Host (External Access):**
| Component | Service | Port | Purpose |
|-----------|---------|------|---------|
| **Orthanc** | Web/API | 9010 | Web UI and REST API |
| | OHIF Viewer | 9012 | Clinical image viewer |
| | DICOM | **4242** | C-STORE from external modalities |
| **Mercure** | Web UI | 9020 | Job management interface |
| | DICOM Receiver | 11112 | Receive DICOM from Orthanc |
| **Monitoring** | Grafana | 9030 | Metrics dashboard |

**Internal Only (Service Name Access):**
| Component | Service | Port | Access Via |
|-----------|---------|------|-----------|
| **Orthanc** | PostgreSQL | 9013 | `orthanc-db` service name |
| **Mercure** | PostgreSQL | 9022 | `mercure_db_1` service name |
| **Monitoring** | Workflow API | 9031 | `workflow-api` service name |
| | Prometheus | 9033 | `prometheus` service name |
| | PostgreSQL | 9042 | `postgres` service name |
| | Graphite | 9038-9041 | `graphite` service name |

**Network Architecture:**
- All services run on a shared Docker network: `leglength-network`
- Containers communicate using service names (e.g., `http://workflow-api:9031`)
- Database ports are NOT exposed to the host for security
- Only necessary interface ports are exposed

---

## 1. Fresh Install

### Step 1: Clone Repository

```bash
# Clone to desired location
cd /opt  # or your preferred directory
sudo git clone <repository-url> leglength-deployment
cd leglength-deployment

# Set ownership (if not running as root)
sudo chown -R $USER:$USER .
```

### Step 2: Create Configuration

```bash
# Create config.env from template
make init

# Edit with your values (passwords, storage paths, etc.)
nano config.env  # or vim/your preferred editor
```

**Required edits in `config.env`:**
- All passwords (generate secure ones: `openssl rand -base64 24`)
- Storage paths (use absolute paths):
  - `ORTHANC_STORAGE` - Orthanc DICOM storage
  - `ORTHANC_DB_STORAGE` - Orthanc PostgreSQL data
  - `MERCURE_DB_PATH` - Mercure PostgreSQL data
  - `MONITORING_DB_STORAGE` - Monitoring PostgreSQL data
- Port assignments (if defaults conflict)

### Step 3: Generate Component Configs

```bash
# Generate all component-specific configs from config.env
sudo make setup
```

This creates:
- `orthanc/.env` and `orthanc/config/orthanc.json`
- `monitoring-v2/.env` and Grafana datasources
- `mercure/config-generated/*` files
- Creates shared Docker network: `leglength-network`
- **Automatically installs Mercure** to `/opt/mercure` (if not already installed)

**Note:** 
- Mercure installation happens automatically during `make setup` using `install_rhel_v2.sh`
- The shared network `leglength-network` is created automatically if it doesn't exist
- All services will join this network for inter-container communication

### Step 4: Build AI Module

```bash
# Build the Docker image for the AI module
make ai-build

# Verify model loading works
make ai-test
```

### Step 5: Start Services

```bash
# Start all services in order
sudo make monitoring-start   # Start monitoring stack first
sudo make orthanc-start      # Then Orthanc
sudo make mercure-start      # Finally Mercure
```

**Or start all at once:**
```bash
sudo make start-all
```

### Step 6: Verify Installation

```bash
# Verify all services are healthy
make verify

# Or check individually:
make status    # Show service status
make urls      # Show service URLs
```

### Step 7: Initial Configuration

1. **Orthanc**: Access http://localhost:9010, login with credentials from `config.env`
2. **OHIF Viewer**: Access http://localhost:9012 to view DICOM images
3. **Mercure**: Access http://localhost:9020, configure processing rules
4. **Grafana**: Access http://localhost:9030, login (default: admin/admin123, change on first login)

---

## 2. Fresh Install After Clearing Everything

Use this when you need to completely wipe and reinstall.

### Step 1: Stop All Services

```bash
sudo make stop-all
```

### Step 2: Clear All Data

**⚠️ WARNING: This permanently deletes all data!**

```bash
# Clear Orthanc
sudo make orthanc-stop
sudo make orthanc-clear  # Confirms before deleting

# Clear Mercure
sudo make mercure-stop
sudo make mercure-clear  # Confirms before deleting

# Clear Monitoring
sudo make monitoring-stop
sudo make monitoring-clear  # Confirms before deleting
```

**Or clear everything at once:**
```bash
sudo make clean-all  # DANGER: Removes everything
```

### Step 3: Remove Generated Configs

```bash
# Remove generated config files (will be regenerated)
make clean-configs
```

### Step 4: Reinstall

Follow steps from [Fresh Install](#1-fresh-install) starting from Step 2 (Create Configuration).

**Quick reinstall sequence:**
```bash
# 1. Update config.env if needed
nano config.env

# 2. Regenerate configs (Mercure will be reinstalled automatically)
sudo make setup

# 3. Rebuild AI module (if code changed)
make ai-build

# 4. Start services
sudo make start-all

# 5. Verify installation
make verify
```

---

## 3. Updates

### Code Updates (Git Pull)

```bash
# Pull latest code
git pull origin main  # or your branch

# Regenerate configs (in case templates changed)
sudo make setup

# Rebuild AI module (if code changed)
make ai-build

# Restart affected services
sudo make restart-all

# Verify everything still works
make verify
```

### Configuration Updates

```bash
# 1. Edit master config
nano config.env

# 2. Regenerate component configs
sudo make setup

# 3. Restart services to apply changes
sudo make restart-all

# 4. Verify services are healthy
make verify

# Or restart individual service:
sudo make orthanc-restart
sudo make monitoring-restart
```

### AI Module Updates

```bash
# 1. Pull latest code
cd mercure-pediatric-leglength
git pull

# 2. Rebuild image
cd ..
make ai-build

# 3. Test model loading
make ai-test

# 4. Update Mercure registry (if model names changed)
# Edit mercure-pediatric-leglength/registry.json if needed

# 5. Restart Mercure to pick up new image
sudo make mercure-restart
```

### Database Migrations

If database schema changes are needed:

```bash
# Stop services
sudo make stop-all

# Backup databases (recommended)
# Orthanc DB: backup orthanc/.env POSTGRES_STORAGE directory
# Monitoring DB: backup monitoring-v2 volumes
# Mercure DB: backup /opt/mercure/db

# Apply migrations (if any migration scripts exist)
# Then restart services
sudo make start-all
```

---

## 4. Debugging Workflow

### Check Service Status

```bash
# Overall status
make status

# Individual service status
sudo make orthanc-ps
sudo make mercure-ps
sudo make monitoring-ps

# All containers
make ps
```

### View Logs

```bash
# Follow logs for a service
sudo make orthanc-logs
sudo make mercure-logs
sudo make monitoring-logs

# Or use docker compose directly
cd orthanc && sudo docker compose logs -f --tail=100
cd /opt/mercure && sudo docker compose logs -f --tail=100
cd monitoring-v2 && sudo docker compose logs -f --tail=100
```

### Common Issues

#### Services Won't Start

```bash
# 1. Check if ports are in use
sudo netstat -tulpn | grep -E ':(4242|9010|9012|9020|9030|11112)'

# 2. Check Docker daemon
sudo systemctl status docker

# 3. Check disk space
df -h

# 4. Check Docker logs
sudo journalctl -u docker.service -n 50
```

#### Configuration Errors

```bash
# 1. Verify config.env is valid
source config.env && echo "Config loaded"

# 2. Regenerate configs
sudo make setup

# 3. Check generated configs
cat orthanc/.env
cat monitoring-v2/.env
```

#### Database Connection Issues

```bash
# 1. Check if databases are running
sudo docker ps | grep postgres

# 2. Check database logs
sudo docker logs <postgres-container-name>

# 3. Test connection
sudo docker exec -it <postgres-container> psql -U <user> -d <database>
```

#### AI Module Issues

```bash
# 1. Test model loading
cd mercure-pediatric-leglength
python3 test_model_loading.py

# 2. Check Docker image
sudo docker images | grep pediatric-leglength

# 3. Test container manually
sudo docker run --rm -it \
  -v $(pwd):/app/v0 \
  stanfordaide/pediatric-leglength:latest \
  python3 test_model_loading.py

# 4. Check Mercure job logs
# Access Mercure UI at http://localhost:9020
# Check "Jobs" tab for failed jobs
```

#### Network Issues

```bash
# 1. Check shared Docker network exists
sudo docker network ls | grep leglength-network
sudo docker network inspect leglength-network

# 2. Verify all containers are on the network
sudo docker network inspect leglength-network | grep -A 5 "Containers"

# 3. Test connectivity between containers using service names
sudo docker exec -it orthanc ping workflow-api
sudo docker exec -it orthanc ping graphite
sudo docker exec -it orthanc ping mercure_db_1

# 4. Check service name resolution
sudo docker exec -it orthanc nslookup workflow-api
```

### Debugging Specific Components

#### Orthanc

```bash
# Check Orthanc system info
curl -u <user>:<pass> http://localhost:9010/system

# Check Orthanc statistics
curl -u <user>:<pass> http://localhost:9010/statistics

# View Orthanc configuration
cat orthanc/config/orthanc.json | jq .

# Test DICOM receive
# Send test DICOM to localhost:4242

# Test connectivity to Workflow API (internal)
sudo docker exec -it orthanc curl http://workflow-api:9031/health
```

#### Mercure

```bash
# Check Mercure status
curl http://localhost:9020/api/status

# View Mercure config
cat /opt/mercure/config/mercure.json | jq .

# Check Mercure database
sudo docker exec -it <mercure-db-container> psql -U mercure -d mercure

# View recent jobs
# Access Mercure UI: http://localhost:9020
```

#### Monitoring Stack

```bash
# Check Grafana datasources
# Access: http://localhost:9030 → Configuration → Data Sources

# Check Prometheus targets (internal access)
sudo docker exec -it prometheus wget -qO- http://localhost:9090/api/v1/targets

# Check PostgreSQL connections
sudo docker exec -it monitoring-postgres psql -U monitoring -d monitoring

# Test workflow API (internal access)
sudo docker exec -it workflow-api curl http://localhost:9031/health
# Or from another container on the network:
sudo docker exec -it orthanc curl http://workflow-api:9031/health
```

### Reset Individual Service

```bash
# Example: Reset Orthanc
sudo make orthanc-stop
sudo make orthanc-clear
sudo make setup
sudo make orthanc-start

# Example: Reset Monitoring
sudo make monitoring-stop
sudo make monitoring-clear
sudo make setup
sudo make monitoring-start
```

### Full System Reset

```bash
# 1. Stop everything
sudo make stop-all

# 2. Clear everything (with confirmation)
sudo make clean-all

# 3. Follow Fresh Install steps from Step 2
```

---

## Quick Reference

### Essential Commands

```bash
# Status & Info
make status              # Show all service status
make urls                # Show service URLs
make ps                  # Show running containers
make verify              # Verify all services are healthy

# Start/Stop
sudo make start-all      # Start all services
sudo make stop-all       # Stop all services
sudo make restart-all    # Restart all services

# Individual Services
sudo make <service>-start    # Start: orthanc, mercure, monitoring
sudo make <service>-stop     # Stop
sudo make <service>-restart  # Restart
sudo make <service>-logs     # View logs
sudo make <service>-ps       # List containers

# Configuration
sudo make setup          # Regenerate all configs from config.env
sudo make <service>-setup    # Setup individual service

# Cleanup
sudo make <service>-clear    # Clear service data (requires stop first)
sudo make clean-configs      # Remove generated config files
sudo make clean-all      # DANGER: Remove everything

# AI Module
make ai-build            # Build Docker image
make ai-test             # Test model loading
make ai-info             # Show image info
```

### Service URLs

| Service | URL | Default Credentials |
|---------|-----|---------------------|
| Orthanc Web/API | http://localhost:9010 | From config.env |
| OHIF Viewer | http://localhost:9012 | - |
| Mercure UI | http://localhost:9020 | - |
| Grafana | http://localhost:9030 | admin/admin123 (change on first login) |
| Orthanc DICOM | localhost:4242 | DICOM C-STORE |
| Mercure DICOM Receiver | localhost:11112 | DICOM C-STORE |

**Internal Services (not exposed to host):**
- Workflow API: `http://workflow-api:9031` (accessible from containers)
- Prometheus: `http://prometheus:9090` (accessible from containers)
- All PostgreSQL databases: accessible via service names

---

## Troubleshooting Checklist

- [ ] Docker daemon running? (`sudo systemctl status docker`)
- [ ] Ports available? (`sudo netstat -tulpn | grep <port>`)
- [ ] Disk space sufficient? (`df -h`)
- [ ] `config.env` exists and is valid? (`source config.env`)
- [ ] Configs regenerated? (`sudo make setup`)
- [ ] Services started in order? (monitoring → orthanc → mercure)
- [ ] Containers running? (`make ps`)
- [ ] Logs show errors? (`sudo make <service>-logs`)
- [ ] Network exists? (`sudo docker network ls | grep leglength-network`)
- [ ] All containers on shared network? (`sudo docker network inspect leglength-network`)
- [ ] Service name resolution working? (`sudo docker exec -it <container> nslookup <service>`)
- [ ] Database connections? (check container logs)
- [ ] Database volumes persisted? (check paths in `config.env`)

---

## Getting Help

1. Check logs: `sudo make <service>-logs`
2. Check status: `make status`
3. Review configuration: `cat <service>/.env`
4. Verify network: `sudo docker network inspect leglength-network`
5. Check component READMEs:
   - `orthanc/README.md`
   - `mercure/README.md`
   - `monitoring-v2/README.md`
6. Review `NETWORK_ARCHITECTURE.md` for network details
7. Review `CHANGES.md` for recent changes

## Network Architecture

All services run on a shared Docker network (`leglength-network`) for secure inter-container communication:

- **Service Discovery**: Containers communicate using service names (e.g., `workflow-api`, `graphite`, `mercure_db_1`)
- **Security**: Database ports are NOT exposed to the host
- **Isolation**: Only necessary interface ports are exposed (4242, 9010, 9012, 9020, 9030, 11112)
- **Persistence**: All database volumes use bind mounts to host paths (configurable via `config.env`)

For detailed network architecture, see `NETWORK_ARCHITECTURE.md`.
