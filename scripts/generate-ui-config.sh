#!/bin/bash
# Generate monitoring UI configuration from config.env
# Called by setup-config.sh after loading config.env

set -e

CONFIG_FILE="${1:-.env}"
OUTPUT_FILE="${2:-monitoring/ui/config-generated.js}"

if [ ! -f "$CONFIG_FILE" ]; then
    echo "ERROR: Config file not found: $CONFIG_FILE"
    exit 1
fi

# Source the config file
set -a
source "$CONFIG_FILE"
set +a

# Generate the JavaScript config
cat > "$OUTPUT_FILE" << 'EOF'
// Auto-generated UI configuration from config.env
// DO NOT EDIT - regenerate with: make setup

window.RADWATCH_CONFIG = {
    // Orthanc PACS server (proxied through nginx /orthanc/)
    orthancUrl: window.location.protocol + '//' + window.location.host + '/orthanc',
    orthancWebUrl: window.location.protocol + '//' + window.location.host + '/orthanc',
    
    // OHIF Viewer (via Orthanc proxy at /ohif/viewer)
    ohifUrl: window.location.protocol + '//' + window.location.host + '/ohif/viewer',
    
    // Grafana for metrics/dashboards
    // Extract hostname from window.location.host (removes port)
    grafanaUrl: window.location.protocol + '//' + window.location.host.split(':')[0] + ':' + GRAFANA_PORT,
    
    // Workflow API (served through nginx proxy at /api/)
    apiBaseUrl: '/api'
};
EOF

# Replace port placeholders with actual values
sed -i "s/GRAFANA_PORT/${GRAFANA_PORT:-9032}/g" "$OUTPUT_FILE"

echo "✓ Generated UI config: $OUTPUT_FILE"
