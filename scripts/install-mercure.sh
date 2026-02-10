#!/bin/bash
# =============================================================================
# Mercure Installation Wrapper
# =============================================================================
# This script ensures the MERCURE_PASSWORD from config.env is used
# =============================================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(dirname "$SCRIPT_DIR")"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

echo -e "${CYAN}Mercure Installation${NC}"
echo ""

# Check if config exists
if [ ! -f "$REPO_ROOT/mercure/config-generated/install.env" ]; then
    echo -e "${RED}ERROR: Mercure config not found!${NC}"
    echo "Run 'make setup' first to generate configuration."
    exit 1
fi

# Source the config to get the password
source "$REPO_ROOT/mercure/config-generated/install.env"

if [ -z "$MERCURE_PASSWORD" ]; then
    echo -e "${RED}ERROR: MERCURE_PASSWORD not set in config${NC}"
    exit 1
fi

echo -e "${GREEN}Using password from config.env${NC}"
echo ""

# Export so sudo -E can see it
export MERCURE_PASSWORD

# Change to mercure directory and run installer
cd "$REPO_ROOT/mercure"

echo -e "${CYAN}Starting Mercure installation...${NC}"
echo ""

# Run with sudo -E to preserve MERCURE_PASSWORD
sudo -E ./install_rhel_v2.sh "$@"
