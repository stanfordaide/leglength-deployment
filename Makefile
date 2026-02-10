# Pediatric Leg Length AI - Deployment Makefile
# Master orchestration for all components

.PHONY: help status start stop restart logs setup clean

# Colors for output
CYAN := \033[36m
GREEN := \033[32m
YELLOW := \033[33m
RED := \033[31m
RESET := \033[0m

help:
	@echo "$(CYAN)Pediatric Leg Length AI - Deployment$(RESET)"
	@echo ""
	@echo "$(GREEN)Getting Started:$(RESET)"
	@echo "  make init            - Create config.env from template"
	@echo "  make setup           - Generate all component configs from config.env"
	@echo ""
	@echo "$(GREEN)Master Commands:$(RESET)"
	@echo "  make status          - Show status of all services"
	@echo "  make start-all       - Start all components"
	@echo "  make stop-all        - Stop all components"
	@echo ""
	@echo "$(GREEN)Individual Components:$(RESET)"
	@echo "  make orthanc-start   - Start Orthanc PACS"
	@echo "  make orthanc-stop    - Stop Orthanc PACS"
	@echo "  make orthanc-logs    - Show Orthanc logs"
	@echo ""
	@echo "  make mercure-start   - Start Mercure orchestrator"
	@echo "  make mercure-stop    - Stop Mercure orchestrator"
	@echo "  make mercure-logs    - Show Mercure logs"
	@echo ""
	@echo "  make ai-build        - Build AI module Docker image"
	@echo ""
	@echo "  make monitoring-start - Start monitoring stack"
	@echo "  make monitoring-stop  - Stop monitoring stack"
	@echo "  make monitoring-logs  - Show monitoring logs"

# =============================================================================
# STATUS
# =============================================================================

status:
	@echo "$(CYAN)====== SERVICE STATUS ======$(RESET)"
	@echo ""
	@echo "$(GREEN)Orthanc:$(RESET)"
	@cd orthanc && docker compose ps 2>/dev/null || echo "  Not configured"
	@echo ""
	@echo "$(GREEN)Mercure:$(RESET)"
	@cd mercure/docker && docker compose ps 2>/dev/null || echo "  Not configured"
	@echo ""
	@echo "$(GREEN)Monitoring:$(RESET)"
	@cd monitoring && docker compose ps 2>/dev/null || echo "  Not configured"
	@echo ""
	@echo "$(GREEN)AI Module:$(RESET)"
	@docker images mercure-pediatric-leglength --format "  Image: {{.Repository}}:{{.Tag}} ({{.Size}})" 2>/dev/null || echo "  Not built"

# =============================================================================
# ALL COMPONENTS
# =============================================================================

start-all: orthanc-start mercure-start monitoring-start
	@echo "$(GREEN)All services started!$(RESET)"

stop-all: monitoring-stop mercure-stop orthanc-stop
	@echo "$(YELLOW)All services stopped.$(RESET)"

# =============================================================================
# ORTHANC
# =============================================================================

orthanc-start:
	@echo "$(CYAN)Starting Orthanc...$(RESET)"
	@cd orthanc && docker compose up -d

orthanc-stop:
	@echo "$(YELLOW)Stopping Orthanc...$(RESET)"
	@cd orthanc && docker compose down

orthanc-logs:
	@cd orthanc && docker compose logs -f

orthanc-shell:
	@cd orthanc && docker compose exec orthanc bash

setup-orthanc:
	@echo "$(CYAN)Setting up Orthanc...$(RESET)"
	@cd orthanc && make setup

# =============================================================================
# MERCURE
# =============================================================================

mercure-start:
	@echo "$(CYAN)Starting Mercure...$(RESET)"
	@cd mercure/docker && docker compose up -d

mercure-stop:
	@echo "$(YELLOW)Stopping Mercure...$(RESET)"
	@cd mercure/docker && docker compose down

mercure-logs:
	@cd mercure/docker && docker compose logs -f

setup-mercure:
	@echo "$(CYAN)To install Mercure, run:$(RESET)"
	@echo ""
	@echo "  make mercure-install"
	@echo ""

# Install Mercure using password from config.env
mercure-install:
	@chmod +x scripts/install-mercure.sh
	@./scripts/install-mercure.sh -y

# =============================================================================
# AI MODULE
# =============================================================================

ai-build:
	@echo "$(CYAN)Building AI module...$(RESET)"
	@cd mercure-pediatric-leglength && docker build -t mercure-pediatric-leglength:latest .
	@echo "$(GREEN)AI module built successfully!$(RESET)"

ai-test:
	@echo "$(CYAN)Testing AI module...$(RESET)"
	@cd mercure-pediatric-leglength && python test_model_loading.py

setup-ai:
	@echo "$(CYAN)Setting up AI module...$(RESET)"
	@cd mercure-pediatric-leglength && pip install -r requirements.txt
	@cd mercure-pediatric-leglength && python download_models.py

# =============================================================================
# MONITORING
# =============================================================================

monitoring-start:
	@echo "$(CYAN)Starting Monitoring...$(RESET)"
	@cd monitoring && docker compose up -d

monitoring-stop:
	@echo "$(YELLOW)Stopping Monitoring...$(RESET)"
	@cd monitoring && docker compose down

monitoring-logs:
	@cd monitoring && docker compose logs -f

setup-monitoring:
	@echo "$(CYAN)Setting up Monitoring...$(RESET)"
	@cd monitoring && make setup

# =============================================================================
# SETUP - Master Configuration
# =============================================================================

# Create config.env from template
init:
	@if [ -f config.env ]; then \
		echo "$(YELLOW)config.env already exists. Remove it first to reinitialize.$(RESET)"; \
	else \
		cp config.env.template config.env; \
		echo "$(GREEN)Created config.env$(RESET)"; \
		echo ""; \
		echo "$(YELLOW)Next steps:$(RESET)"; \
		echo "  1. Edit config.env with your passwords and settings"; \
		echo "  2. Run: make setup"; \
	fi

# Generate all component configs from master config.env
setup:
	@chmod +x scripts/setup-config.sh
	@./scripts/setup-config.sh

# Validate config without generating
setup-check:
	@echo "$(CYAN)Checking configuration...$(RESET)"
	@if [ ! -f config.env ]; then \
		echo "$(RED)config.env not found. Run 'make init' first.$(RESET)"; \
		exit 1; \
	fi
	@source config.env && \
	if [[ "$$ORTHANC_ADMIN_PASS" == CHANGE_ME* ]]; then \
		echo "$(RED)Please update passwords in config.env$(RESET)"; \
		exit 1; \
	fi
	@echo "$(GREEN)Configuration looks good!$(RESET)"

# =============================================================================
# UTILITIES
# =============================================================================

clean:
	@echo "$(RED)WARNING: This will stop and remove all containers!$(RESET)"
	@read -p "Are you sure? [y/N] " confirm && [ "$$confirm" = "y" ] || exit 1
	@cd orthanc && docker compose down -v 2>/dev/null || true
	@cd mercure/docker && docker compose down -v 2>/dev/null || true
	@cd monitoring && docker compose down -v 2>/dev/null || true
	@echo "$(YELLOW)Cleaned.$(RESET)"

# Show all docker containers related to this deployment
ps:
	@docker ps --filter "name=orthanc" --filter "name=mercure" --filter "name=workflow" --filter "name=grafana" --filter "name=prometheus"
