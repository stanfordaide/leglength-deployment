#!/bin/bash
# =============================================================================
# LEGLENGTH DEPLOYMENT - Configuration Setup Script
# =============================================================================
# Reads config.env and generates component-specific configs
# =============================================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(dirname "$SCRIPT_DIR")"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

echo -e "${CYAN}╔════════════════════════════════════════════════════════════╗${NC}"
echo -e "${CYAN}║     LEGLENGTH DEPLOYMENT - Configuration Setup            ║${NC}"
echo -e "${CYAN}╚════════════════════════════════════════════════════════════╝${NC}"
echo ""

# Check if config.env exists
if [ ! -f "$REPO_ROOT/config.env" ]; then
    echo -e "${RED}ERROR: config.env not found!${NC}"
    echo ""
    echo "Please create it first:"
    echo "  cp config.env.template config.env"
    echo "  # Edit config.env with your values"
    echo ""
    exit 1
fi

# Source the master config
source "$REPO_ROOT/config.env"

# Validate required fields
echo -e "${CYAN}Validating configuration...${NC}"
MISSING=0

check_var() {
    local var_name=$1
    local var_value="${!var_name}"
    if [ -z "$var_value" ] || [[ "$var_value" == CHANGE_ME* ]]; then
        echo -e "  ${RED}✗${NC} $var_name is not set or needs to be changed"
        MISSING=1
    else
        echo -e "  ${GREEN}✓${NC} $var_name"
    fi
}

check_var "ORTHANC_ADMIN_PASS"
check_var "ORTHANC_DB_PASS"
check_var "MERCURE_DB_PASS"
check_var "WORKFLOW_DB_PASS"
check_var "GRAFANA_PASS"

if [ $MISSING -eq 1 ]; then
    echo ""
    echo -e "${RED}Please update config.env with proper values before continuing.${NC}"
    exit 1
fi

echo ""
echo -e "${GREEN}Configuration valid!${NC}"
echo ""

# =============================================================================
# Generate Orthanc .env
# =============================================================================
echo -e "${CYAN}Generating orthanc/.env...${NC}"
cat > "$REPO_ROOT/orthanc/.env" << EOF
# Auto-generated from config.env - DO NOT EDIT DIRECTLY
# Re-run 'make setup' to regenerate

# Storage
DICOM_STORAGE=${ORTHANC_DICOM_STORAGE}
POSTGRES_STORAGE=${ORTHANC_DB_STORAGE}

# Credentials
ORTHANC_USERNAME=${ORTHANC_ADMIN_USER}
ORTHANC_PASSWORD=${ORTHANC_ADMIN_PASS}
POSTGRES_USER=${ORTHANC_DB_USER}
POSTGRES_PASSWORD=${ORTHANC_DB_PASS}

# DICOM
ORTHANC_AET=${ORTHANC_AET}
DICOM_PORT=${DICOM_PORT}

# Ports
OPERATOR_UI_PORT=${ORTHANC_OPERATOR_PORT}
ORTHANC_WEB_PORT=${ORTHANC_WEB_PORT}
OHIF_PORT=${ORTHANC_OHIF_PORT}
POSTGRES_PORT=${ORTHANC_DB_PORT}
ROUTING_API_PORT=${ORTHANC_API_PORT}

# Workflow API (Lua scripts use this for tracking)
WORKFLOW_API_URL=${WORKFLOW_API_URL}

# Timezone
TZ=${TZ}
EOF
echo -e "  ${GREEN}✓${NC} orthanc/.env created"

# =============================================================================
# Generate Orthanc orthanc.json (from template)
# =============================================================================
echo -e "${CYAN}Generating orthanc/config/orthanc.json...${NC}"

ORTHANC_JSON_TEMPLATE="$REPO_ROOT/orthanc/config/orthanc.json.template"
ORTHANC_JSON_OUTPUT="$REPO_ROOT/orthanc/config/orthanc.json"

if [ ! -f "$ORTHANC_JSON_TEMPLATE" ]; then
    echo -e "  ${RED}✗${NC} Template not found: $ORTHANC_JSON_TEMPLATE"
    exit 1
fi

# Use envsubst to replace variables in template
# We need to export the variables for envsubst
export ORTHANC_AET ORTHANC_DB_USER ORTHANC_DB_PASS ORTHANC_ADMIN_USER ORTHANC_ADMIN_PASS

# Parse modalities for JSON
# Input: AET|HOST|PORT
# Output: [ "AET", "HOST", PORT ]
format_modality() {
    local val=$1
    if [ -z "$val" ]; then echo "null"; return; fi
    IFS='|' read -r aet host port <<< "$val"
    echo "[ \"$aet\", \"$host\", $port ]"
}

export MODALITY_MERCURE_JSON=$(format_modality "$MODALITY_MERCURE")
export MODALITY_LPCHROUTER_JSON=$(format_modality "$MODALITY_LPCHROUTER")
export MODALITY_LPCHTROUTER_JSON=$(format_modality "$MODALITY_LPCHTROUTER")
export MODALITY_MODLINK_JSON=$(format_modality "$MODALITY_MODLINK")

envsubst '${ORTHANC_AET} ${ORTHANC_DB_USER} ${ORTHANC_DB_PASS} ${ORTHANC_ADMIN_USER} ${ORTHANC_ADMIN_PASS} ${MODALITY_MERCURE_JSON} ${MODALITY_LPCHROUTER_JSON} ${MODALITY_LPCHTROUTER_JSON} ${MODALITY_MODLINK_JSON}' \
    < "$ORTHANC_JSON_TEMPLATE" \
    > "$ORTHANC_JSON_OUTPUT"

echo -e "  ${GREEN}✓${NC} orthanc/config/orthanc.json created"

# =============================================================================
# Generate Orthanc Lua config.lua (from template)
# =============================================================================
echo -e "${CYAN}Generating orthanc/lua-scripts-v2/config.lua...${NC}"

CONFIG_LUA_TEMPLATE="$REPO_ROOT/orthanc/lua-scripts-v2/config.lua.template"
CONFIG_LUA_OUTPUT="$REPO_ROOT/orthanc/lua-scripts-v2/config.lua"

if [ ! -f "$CONFIG_LUA_TEMPLATE" ]; then
    echo -e "  ${RED}✗${NC} Template not found: $CONFIG_LUA_TEMPLATE"
    exit 1
fi

# Use envsubst to replace WORKFLOW_API_URL in template
export WORKFLOW_API_URL

envsubst '${WORKFLOW_API_URL}' \
    < "$CONFIG_LUA_TEMPLATE" \
    > "$CONFIG_LUA_OUTPUT"

echo -e "  ${GREEN}✓${NC} orthanc/lua-scripts-v2/config.lua created"

# =============================================================================
# Generate Mercure db.env (for pre-installation)
# =============================================================================
echo -e "${CYAN}Generating mercure config for installation...${NC}"

# Create the db.env that Mercure installer will use
mkdir -p "$REPO_ROOT/mercure/config-generated"
cat > "$REPO_ROOT/mercure/config-generated/db.env" << EOF
POSTGRES_PASSWORD=${MERCURE_DB_PASS}
EOF

# Create env vars file for installer
cat > "$REPO_ROOT/mercure/config-generated/install.env" << EOF
# Source this before running install_rhel_v2.sh
export MERCURE_PASSWORD="${MERCURE_DB_PASS}"
export MERCURE_BASE=/opt/mercure
EOF

echo -e "  ${GREEN}✓${NC} mercure/config-generated/db.env created"
echo -e "  ${GREEN}✓${NC} mercure/config-generated/install.env created"

# =============================================================================
# Generate Mercure mercure.json
# =============================================================================
echo -e "${CYAN}Generating mercure/config-generated/mercure.json...${NC}"

MERCURE_JSON_TEMPLATE="$REPO_ROOT/mercure/config/mercure.json.template"
MERCURE_JSON_OUTPUT="$REPO_ROOT/mercure/config-generated/mercure.json"

# Create a template if it doesn't exist (using the one we just defined in the previous step as a base)
if [ ! -f "$MERCURE_JSON_TEMPLATE" ]; then
    echo -e "  ${YELLOW}⚠ Template not found: $MERCURE_JSON_TEMPLATE. Creating default template...${NC}"
    mkdir -p "$REPO_ROOT/mercure/config"
    cat > "$MERCURE_JSON_TEMPLATE" << 'EOF'
{
    "appliance_name": "master",
    "appliance_color": "#FFF",
    "port": 11112,
    "accept_compressed_images": false,
    "incoming_folder": "/opt/mercure/data/incoming",
    "studies_folder": "/opt/mercure/data/studies",
    "outgoing_folder": "/opt/mercure/data/outgoing",
    "success_folder": "/opt/mercure/data/success",
    "error_folder": "/opt/mercure/data/error",
    "discard_folder": "/opt/mercure/data/discard",
    "processing_folder": "/opt/mercure/data/processing",
    "jobs_folder": "/opt/mercure/data/jobs",
    "router_scan_interval": 1,
    "dispatcher_scan_interval": 1,
    "cleaner_scan_interval": 60,
    "retention": 259200,
    "emergency_clean_percentage": 90,
    "retry_delay": 900,
    "retry_max": 5,
    "series_complete_trigger": 60,
    "study_complete_trigger": 900,
    "study_forcecomplete_trigger": 5400,
    "dicom_receiver": {
        "additional_tags": {}
    },
    "graphite_ip": "172.17.0.1",
    "graphite_port": 9038,
    "influxdb_host": "",
    "influxdb_token": "",
    "influxdb_org": "",
    "influxdb_bucket": "",
    "bookkeeper": "bookkeeper:8080",
    "offpeak_start": "22:00",
    "offpeak_end": "06:00",
    "targets": {
        "OrthancLPCH": {
            "target_type": "dicom",
            "contact": "",
            "comment": "",
            "direction": "both",
            "ip": "172.17.0.1",
            "port": "4242",
            "aet_target": "ORTHANC_LPCH",
            "aet_source": "MERCURE",
            "pass_sender_aet": false,
            "pass_receiver_aet": false
        }
    },
    "rules": {
        "LegLengthRule": {
            "rule": "\"EXTREMITY BILATERAL BONE LENGTH\" in tags.StudyDescription",
            "target": [
                "OrthancLPCH"
            ],
            "disabled": false,
            "fallback": false,
            "contact": "",
            "comment": "Default rule: \"EXTREMITY BILATERAL BONE LENGTH\" in tags.StudyDescription",
            "tags": "",
            "action": "both",
            "action_trigger": "series",
            "study_trigger_condition": "timeout",
            "study_force_completion_action": "discard",
            "study_trigger_series": "",
            "priority": "normal",
            "processing_module": [
                "PediatricLegLength"
            ],
            "processing_settings": {},
            "processing_retain_images": false,
            "notification_email": "",
            "notification_webhook": "",
            "notification_payload": "",
            "notification_payload_body": "Rule \"{{ rule }}\" triggered {{ event }}\r\n{% if details is defined and details|length %}\r\nDetails:\r\n{{ details }}\r\n{% endif %}",
            "notification_email_body": "Rule \"{{ rule }}\" triggered {{ event }}\r\nName: {{ patient_name }}\r\nACC: {{ acc }}\r\nMRN: {{ mrn }}\r\n{% if details is defined and details|length %}\r\nDetails:\r\n{{ details }}\r\n{% endif %}",
            "notification_email_type": "plain",
            "notification_trigger_reception": true,
            "notification_trigger_completion": true,
            "notification_trigger_completion_on_request": false,
            "notification_trigger_error": true
        }
    },
    "modules": {
        "PediatricLegLength": {
            "docker_tag": "stanfordaide/pediatric-leglength:latest",
            "additional_volumes": "${MONITORING_DATA_PATH}:${MONITORING_DATA_PATH}",
            "environment": "MONITORING_DATA_PATH=${MONITORING_DATA_PATH}",
            "docker_arguments": "",
            "settings": {
                "models": [
                    "rn50adncti",
                    "rn50adkpncti",
                    "rn50adkp"
                ],
                "series_offset": 1000,
                "femur_threshold": 0.2,
                "tibia_threshold": 0.2,
                "total_threshold": 1,
                "confidence_threshold": 0,
                "monitoring": {
                    "enabled": true,
                    "metrics": {
                        "collection_interval": 10,
                        "batch_size": 50,
                        "include_system_metrics": true,
                        "include_model_metrics": true
                    },
                    "backends": {
                        "file": {
                            "enabled": true,
                            "path": "${MONITORING_DATA_PATH}"
                        },
                        "mercure": {
                            "enabled": true
                        }
                    }
                }
            },
            "contact": "arogya@stanford.edu",
            "comment": "Pediatric Leg Length Module",
            "constraints": "",
            "resources": "",
            "requires_root": false
        }
    },
    "process_runner": "docker",
    "processing_runtime": null,
    "bookkeeper_api_key": "lfY1tFLnivdp5tcIQ319JlD4INZWCiYW",
    "features": {
        "dummy_target": false
    },
    "processing_logs": {
        "discard_logs": false,
        "logs_file_store": null
    },
    "email_notification_from": "mercure@mercure.mercure",
    "support_root_modules": false,
    "webhook_certificate_location": null,
    "phi_notifications": false,
    "server_time": "America/Los_Angeles",
    "local_time": "America/Los_Angeles",
    "dicom_retrieve": {
        "dicom_nodes": [],
        "destination_folders": []
    },
    "store_sample_dicom_tags": false
}
EOF
fi

# Use envsubst to replace MONITORING_DATA_PATH in template
export MONITORING_DATA_PATH

envsubst '${MONITORING_DATA_PATH}' \
    < "$MERCURE_JSON_TEMPLATE" \
    > "$MERCURE_JSON_OUTPUT"

echo -e "  ${GREEN}✓${NC} mercure/config-generated/mercure.json created"

# =============================================================================
# Generate Monitoring .env
# =============================================================================
echo -e "${CYAN}Generating monitoring/.env...${NC}"
cat > "$REPO_ROOT/monitoring/.env" << EOF
# Auto-generated from config.env - DO NOT EDIT DIRECTLY
# Re-run 'make setup-config' to regenerate

# Workflow Tracking
WORKFLOW_UI_PORT=${MONITORING_UI_PORT}
WORKFLOW_API_PORT=${MONITORING_API_PORT}
WORKFLOW_DB_NAME=workflow_tracking
WORKFLOW_DB_USER=${WORKFLOW_DB_USER}
WORKFLOW_DB_PASS=${WORKFLOW_DB_PASS}

# Orthanc Connection
ORTHANC_URL=http://${DOCKER_HOST_GATEWAY}:${ORTHANC_WEB_PORT}
ORTHANC_USER=${ORTHANC_ADMIN_USER}
ORTHANC_PASS=${ORTHANC_ADMIN_PASS}

# Orthanc Database
ORTHANC_DB_HOST=${DOCKER_HOST_GATEWAY}
ORTHANC_DB_PORT=${ORTHANC_DB_PORT}
ORTHANC_DB_USER=${ORTHANC_DB_USER}
ORTHANC_DB_PASS=${ORTHANC_DB_PASS}

# Mercure Database
MERCURE_DB_HOST=${DOCKER_HOST_GATEWAY}
MERCURE_DB_PORT=${MERCURE_DB_PORT}
MERCURE_DB_NAME=mercure
MERCURE_DB_USER=${MERCURE_DB_USER}
MERCURE_DB_PASS=${MERCURE_DB_PASS}

# Mercure Bookkeeper Database (for workflow recovery and analytics)
BOOKKEEPER_DB_HOST=${DOCKER_HOST_GATEWAY}
BOOKKEEPER_DB_PORT=${MERCURE_DB_PORT}
BOOKKEEPER_DB_NAME=mercure
BOOKKEEPER_DB_USER=${MERCURE_DB_USER}
BOOKKEEPER_DB_PASS=${MERCURE_DB_PASS}

# Orthanc API Connection (for workflow filtering)
ORTHANC_API_URL=http://${DOCKER_HOST_GATEWAY}:${ORTHANC_WEB_PORT}
ORTHANC_USERNAME=${ORTHANC_ADMIN_USER}
ORTHANC_PASSWORD=${ORTHANC_ADMIN_PASS}

# Grafana
GRAFANA_PORT=${GRAFANA_PORT}
GRAFANA_USER=${GRAFANA_USER}
GRAFANA_PASS=${GRAFANA_PASS}

# Prometheus & Metrics
PROMETHEUS_PORT=${PROMETHEUS_PORT}
ALERTMANAGER_PORT=${ALERTMANAGER_PORT}
NODE_EXPORTER_PORT=${NODE_EXPORTER_PORT}
CADVISOR_PORT=${CADVISOR_PORT}
PUSHGATEWAY_PORT=${PUSHGATEWAY_PORT}

# Graphite
GRAPHITE_PORT=${GRAPHITE_PORT}
GRAPHITE_PICKLE_PORT=${GRAPHITE_PICKLE_PORT}
STATSD_PORT=${STATSD_PORT}

# Alerting
SLACK_WEBHOOK_URL=${SLACK_WEBHOOK_URL}
SLACK_CHANNEL=${SLACK_CHANNEL}

# Data Path for Harvester
MONITORING_DATA_PATH=${MONITORING_DATA_PATH}
EOF
echo -e "  ${GREEN}✓${NC} monitoring/.env created"

# Generate Monitoring .env
echo -e "${CYAN}Generating monitoring-v2/.env...${NC}"
cat > "$REPO_ROOT/monitoring-v2/.env" << EOF
# Monitoring - Metrics Collection Stack
# Generated from config.env.template by setup-config.sh

# Grafana
GRAFANA_PORT=${GRAFANA_PORT}
GRAFANA_USER=${GRAFANA_USER}
GRAFANA_PASS=${GRAFANA_PASS}

# Prometheus
PROMETHEUS_PORT=${PROMETHEUS_PORT}

# Graphite
GRAPHITE_PORT=${GRAPHITE_PORT}
GRAPHITE_PICKLE_PORT=${GRAPHITE_PICKLE_PORT}
GRAPHITE_WEB_PORT=${GRAPHITE_WEB_PORT}
EOF
echo -e "  ${GREEN}✓${NC} monitoring-v2/.env created"

# =============================================================================
# Set Secure File Permissions
# =============================================================================
echo -e "${CYAN}Setting secure file permissions...${NC}"

# Restrict config.env to owner only (contains secrets)
chmod 600 "$REPO_ROOT/config.env"
echo -e "  ${GREEN}✓${NC} config.env (600 - owner read/write only)"

# Restrict generated .env files
chmod 600 "$REPO_ROOT/orthanc/.env"
echo -e "  ${GREEN}✓${NC} orthanc/.env (600)"

chmod 600 "$REPO_ROOT/orthanc/config/orthanc.json"
echo -e "  ${GREEN}✓${NC} orthanc/config/orthanc.json (600)"

chmod 600 "$REPO_ROOT/monitoring/.env"
echo -e "  ${GREEN}✓${NC} monitoring/.env (600)"

chmod 600 "$REPO_ROOT/monitoring-v2/.env"
echo -e "  ${GREEN}✓${NC} monitoring-v2/.env (600)"

chmod 600 "$REPO_ROOT/mercure/config-generated/db.env"
chmod 600 "$REPO_ROOT/mercure/config-generated/install.env"
chmod 600 "$REPO_ROOT/mercure/config-generated/mercure.json"
echo -e "  ${GREEN}✓${NC} mercure/config-generated/*.env (600)"

# =============================================================================
# Generate UI Configuration
# =============================================================================
echo -e "${CYAN}Generating UI configuration...${NC}"

"$SCRIPT_DIR/generate-ui-config.sh" "$REPO_ROOT/config.env" "$REPO_ROOT/monitoring/ui/config-generated.js"

# =============================================================================
# Summary
# =============================================================================
echo ""
echo -e "${GREEN}╔════════════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║     Configuration Complete!                                ║${NC}"
echo -e "${GREEN}╚════════════════════════════════════════════════════════════╝${NC}"
echo ""
echo "Generated files:"
echo "  • orthanc/.env"
echo "  • orthanc/config/orthanc.json"
echo "  • orthanc/lua-scripts-v2/config.lua"
echo "  • mercure/config-generated/db.env"
echo "  • mercure/config-generated/install.env"
echo "  • mercure/config-generated/mercure.json"
echo "  • monitoring/.env"
echo "  • monitoring-v2/.env"
echo ""
echo -e "${CYAN}Next steps:${NC}"
echo ""
echo "  1. Start Monitoring:    cd monitoring && make start"
echo "  2. Start Orthanc:       cd orthanc && make setup && make start"
echo "  3. Install Mercure:     cd mercure && source config-generated/install.env && sudo ./install_rhel_v2.sh -y"
echo "  4. Build AI Module:     make ai-build"
echo ""
echo -e "${YELLOW}Port Summary:${NC}"
echo "  Orthanc:     http://localhost:${ORTHANC_WEB_PORT}"
echo "  OHIF:        http://localhost:${ORTHANC_OHIF_PORT}"
echo "  Mercure:     http://localhost:${MERCURE_WEB_PORT}"
echo "  Workflow UI: http://localhost:${MONITORING_UI_PORT}"
echo "  Grafana:     http://localhost:${GRAFANA_PORT}"
echo "  DICOM:       ${DICOM_PORT}"
echo ""
