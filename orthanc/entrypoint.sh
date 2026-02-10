#!/bin/bash
# Orthanc startup script - seeds default modalities if they don't exist

set -e

# Parse environment
USERNAME="${ORTHANC_USERNAME:-orthanc_admin}"
PASSWORD="${ORTHANC_PASSWORD:-helloaide123}"
PORT="${ORTHANC_WEB_PORT:-8042}"
URL="http://localhost:$PORT"

# Wait for Orthanc to be ready
echo "[Startup] Waiting for Orthanc to be healthy..."
for i in {1..30}; do
    if curl -sf -u "$USERNAME:$PASSWORD" "$URL/system" > /dev/null 2>&1; then
        echo "[Startup] Orthanc is healthy!"
        break
    fi
    echo "[Startup] Attempt $i/30, waiting..."
    sleep 1
done

# Check if modalities exist
echo "[Startup] Checking for existing modalities..."
MODALITIES=$(curl -s -u "$USERNAME:$PASSWORD" "$URL/modalities" 2>/dev/null || echo "[]")

if [ "$MODALITIES" = "[]" ] || [ -z "$MODALITIES" ]; then
    echo "[Startup] No modalities found, seeding defaults..."
    
    # Seed default modalities
    curl -sf -u "$USERNAME:$PASSWORD" -X PUT "$URL/modalities/MERCURE" \
        -H "Content-Type: application/json" \
        -d '{"AET":"orthanc","Host":"172.17.0.1","Port":11112}' \
        && echo "[Startup] ✓ MERCURE" || echo "[Startup] ✗ MERCURE"
    
    curl -sf -u "$USERNAME:$PASSWORD" -X PUT "$URL/modalities/LPCHROUTER" \
        -H "Content-Type: application/json" \
        -d '{"AET":"LPCHROUTER","Host":"10.50.133.21","Port":4000}' \
        && echo "[Startup] ✓ LPCHROUTER" || echo "[Startup] ✗ LPCHROUTER"
    
    curl -sf -u "$USERNAME:$PASSWORD" -X PUT "$URL/modalities/LPCHTROUTER" \
        -H "Content-Type: application/json" \
        -d '{"AET":"LPCHTROUTER","Host":"10.50.130.114","Port":4000}' \
        && echo "[Startup] ✓ LPCHTROUTER" || echo "[Startup] ✗ LPCHTROUTER"
    
    curl -sf -u "$USERNAME:$PASSWORD" -X PUT "$URL/modalities/MODLINK" \
        -H "Content-Type: application/json" \
        -d '{"AET":"PSRTBONEAPP01","Host":"10.251.201.59","Port":104}' \
        && echo "[Startup] ✓ MODLINK" || echo "[Startup] ✗ MODLINK"
    
    echo "[Startup] Modalities seeded!"
else
    echo "[Startup] Modalities already exist, skipping seed"
fi

echo "[Startup] Ready!"
