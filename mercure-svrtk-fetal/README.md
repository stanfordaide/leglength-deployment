# SVRTK Fetal MRI Processing Module

This module integrates the SVRTK (Slice-to-Volume Reconstruction ToolKit) fetal MRI processing pipeline into the unified leglength-deployment framework.

## Overview

The SVRTK module automatically processes fetal MRI studies with intelligent series grouping and parallel reconstruction:

- **Input**: Complete fetal MRI studies from Orthanc PACS
- **Processing**: Intelligent categorization and SVRTK reconstruction  
- **Output**: Reconstructed DICOM series returned to Orthanc and forwarded to PACS

## Architecture

```
┌─────────────────┐     ┌───────────────────┐     ┌──────────────────┐
│   Orthanc PACS  │────▶│  Mercure Queue   │────▶│   SVRTK Module   │
│  Lua Detection  │◀────│  Job Dispatch    │◀────│   v8 Container   │
└─────────────────┘     └───────────────────┘     └──────────────────┘
```

## Components

### 1. Container: SVRTK v8
- **Image**: `localhost/svrtk:openjpeg-embedded-nii2dcm-fixed-v8`
- **Status**: Working baseline, migrated from existing setup
- **Features**: Complete SVRTK toolkit with OpenJPEG and nii2dcm support

### 2. Processor: `intelligent_svrtk_processor.py`  
- **Function**: Analyzes series descriptions and runs targeted reconstructions
- **Categories**: 
  - SSFSEx Brain/Body
  - FIESTA Brain/Body
- **Output**: Up to 4 separate SVRTK reconstructions per study

### 3. Lua Router: `autosend_svrtk_fetal.lua`
- **Detection**: Identifies fetal MRI studies automatically
- **Routing**: Sends studies to Mercure for SVRTK processing
- **Results**: Auto-forwards reconstructions to LPCHROUTER PACS

## Configuration

### Environment Variables (config.env)
```bash
# SVRTK Container  
SVRTK_DOCKER_IMAGE=localhost/svrtk:openjpeg-embedded-nii2dcm-fixed-v8
SVRTK_VERSION=8
SVRTK_TIMEOUT=300
SVRTK_WORKERS=8

# PACS Integration
SVRTK_TARGET_PACS=LPCHROUTER
LPCHROUTER_HOST=localhost
LPCHROUTER_PORT=104
```

### Mercure Configuration
- **Timeout**: 300 seconds for large studies (2000+ instances)
- **Workers**: 8 concurrent fast workers 
- **Action**: `process` (results returned to source)

## Migration from Old Setup

This module was migrated from the previous standalone setup:

### Before (Scattered Deployment)
```
/opt/mercure/config/mercure.json          # Standalone config
/opt/mercure/config/lua/autosend_*.lua    # Separate Lua scripts  
/home/amosinha/SVRTK/processor.py         # Manual processor
Docker containers: localhost/svrtk:*      # Multiple versions
```

### After (Unified Framework) 
```
leglength-deployment/
├── config.env.template                   # Unified configuration
├── mercure-svrtk-fetal/                 # SVRTK module
│   ├── Dockerfile                       # v8 container setup
│   ├── processor/intelligent_*.py       # Migrated processor
│   └── config/autosend_*.lua           # Integrated Lua router
└── Makefile                             # Automated management
```

## Usage

### Start Services
```bash
cd /home/amosinha/leglength-deployment
sudo make setup                    # Generate configs
sudo make start-all                # Start all services  
make status                        # Check status
```

### Process Studies  
```bash
# Send study by UID (automatic via Lua)
python3 scripts/send_study.py 1.2.840.114350.2.349.2.798268.2.856239038.1

# Manual Mercure processing
curl -X POST http://localhost:9020/studies/process \
     -H "Content-Type: application/json" \
     -d '{"study_uid": "1.2.840..."}'
```

### Monitor Processing
```bash 
# View logs
sudo make mercure-logs
docker logs mercure_worker_fast_1

# Web interfaces  
open http://localhost:9020          # Mercure UI
open http://localhost:9030          # Workflow Monitor  
open http://localhost:9011          # Orthanc Web
```

## Processing Workflow

1. **Study Arrival**: Fetal MRI study reaches Orthanc (port 4242)
2. **Auto-Detection**: Lua script identifies fetal characteristics
3. **Queue Job**: Entire study sent to Mercure for processing  
4. **Smart Analysis**: Processor categorizes series by description
5. **Parallel Reconstruction**: Up to 4 SVRTK jobs run simultaneously
6. **Result Return**: Reconstructed series added to same Orthanc study
7. **PACS Forward**: Results auto-forwarded to LPCHROUTER (port 104)

## Supported Series Types

### Input Series (Auto-detected)
- **SSFSEx Brain**: T2-weighted single-shot fast spin echo, brain
- **SSFSEx Body**: T2-weighted single-shot fast spin echo, body/abdomen  
- **FIESTA Brain**: Fast imaging employing steady-state acquisition, brain
- **FIESTA Body**: Fast imaging employing steady-state acquisition, body

### Output Series (Generated)
- `SVRTK SSFSEx Brain Reconstruction`
- `SVRTK SSFSEx Body Reconstruction`  
- `SVRTK FIESTA Brain Reconstruction`
- `SVRTK FIESTA Body Reconstruction`

## Troubleshooting

### Common Issues
```bash
# Check container status
docker ps | grep svrtk

# Restart SVRTK processing  
sudo make mercure-restart

# Check worker logs for errors
docker logs mercure_worker_fast_1 2>&1 | grep -i error

# Verify PACS connectivity
curl -u orthanc_admin:helloaide123 http://localhost:9011/modalities/LPCHROUTER
```

### Study Timeouts
If large studies (>2000 instances) timeout:
1. Increase `SVRTK_TIMEOUT` in config.env
2. Run `sudo make setup && sudo make mercure-restart`

### Container Issues  
If v8 container fails:
```bash
# Check image availability
docker images | grep svrtk.*v8

# Rebuild SVRTK module
cd mercure-svrtk-fetal && docker build -t mercure-svrtk-fetal .
```

## Performance
- **Small Studies** (<500 instances): ~5-10 minutes
- **Medium Studies** (500-1500 instances): ~15-30 minutes  
- **Large Studies** (>1500 instances): ~30-60 minutes
- **Parallel Processing**: Up to 4 reconstructions simultaneously

## Integration Benefits

✅ **Unified Management**: Single `make` commands for everything  
✅ **Standardized Configs**: Template-driven, version controlled
✅ **Built-in Monitoring**: Grafana dashboards + Prometheus metrics
✅ **Production Ready**: Proper logging, error handling, recovery
✅ **Scalable Architecture**: Easy to add more AI modules