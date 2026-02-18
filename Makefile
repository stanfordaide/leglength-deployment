# Pediatric Leg Length AI - Deployment Makefile
# Master orchestration for all components
#
# PATTERN:
#   Services (orthanc, mercure, monitoring): start, stop, setup, ps, logs, clear
#   Build artifacts (ai): build, test, push, clean, info

.PHONY: help status urls start-all stop-all \
        orthanc-start orthanc-stop orthanc-logs orthanc-clear orthanc-setup orthanc-ps \
        mercure-start mercure-stop mercure-logs mercure-clear mercure-setup mercure-ps \
        monitoring-start monitoring-stop monitoring-logs monitoring-clear monitoring-setup monitoring-ps \
        ai-build ai-test ai-push ai-clean ai-info \
        init setup setup-config clean clean-all ps

# Colors (using printf-compatible format)
CYAN    := \033[36m
GREEN   := \033[32m
YELLOW  := \033[33m
RED     := \033[31m
BOLD    := \033[1m
RESET   := \033[0m

# =============================================================================
# HELP
# =============================================================================

help:
	@printf "$(BOLD)$(CYAN)Pediatric Leg Length AI - Deployment$(RESET)\n"
	@printf "\n"
	@printf "$(BOLD)Global Commands:$(RESET)\n"
	@printf "  make status            Show status of all services\n"
	@printf "  make urls              Show all service URLs\n"
	@printf "  make start-all         Start all components\n"
	@printf "  make stop-all          Stop all components\n"
	@printf "  make ps                Show running containers\n"
	@printf "\n"
	@printf "$(BOLD)Services:$(RESET)\n"
	@printf "\n"
	@printf "  $(GREEN)Orthanc$(RESET) - DICOM PACS Server\n"
	@printf "    make orthanc-start   Start Orthanc\n"
	@printf "    make orthanc-stop    Stop Orthanc\n"
	@printf "    make orthanc-setup   Setup Orthanc (create dirs from .env)\n"
	@printf "    make orthanc-ps      List Orthanc containers\n"
	@printf "    make orthanc-logs    View Orthanc logs (follow)\n"
	@printf "    make orthanc-clear   $(YELLOW)Clear all data (requires stop first)$(RESET)\n"
	@printf "\n"
	@printf "  $(GREEN)Mercure$(RESET) - AI Job Orchestrator\n"
	@printf "    make mercure-start   Start Mercure\n"
	@printf "    make mercure-stop    Stop Mercure\n"
	@printf "    make mercure-setup   Setup Mercure (verify installation)\n"
	@printf "    make mercure-ps      List Mercure containers\n"
	@printf "    make mercure-logs    View Mercure logs (follow)\n"
	@printf "    make mercure-clear   $(YELLOW)Clear all data (requires stop first)$(RESET)\n"
	@printf "\n"
	@printf "  $(GREEN)Monitoring$(RESET) - Grafana, Prometheus, Graphite\n"
	@printf "    make monitoring-start   Start monitoring stack\n"
	@printf "    make monitoring-stop    Stop monitoring stack\n"
	@printf "    make monitoring-setup   Setup monitoring (create dirs, verify config)\n"
	@printf "    make monitoring-ps      List monitoring containers\n"
	@printf "    make monitoring-logs    View monitoring logs (follow)\n"
	@printf "    make monitoring-clear   $(YELLOW)Clear all data (requires stop first)$(RESET)\n"
	@printf "\n"
	@printf "$(BOLD)AI Module (build/test/push/clean/info):$(RESET)\n"
	@printf "    make ai-build        Build Docker image\n"
	@printf "    make ai-test         Test model loading\n"
	@printf "    make ai-push         Push to registry\n"
	@printf "    make ai-clean        Remove old images\n"
	@printf "    make ai-info         Show image info\n"
	@printf "\n"
	@printf "$(BOLD)Setup (run in order):$(RESET)\n"
	@printf "    make init            $(CYAN)Create config.env from template (first time only)$(RESET)\n"
	@printf "    nano config.env      Edit passwords and paths\n"
	@printf "    make setup           Generate all component configs from config.env\n"
	@printf "    make <service>-setup Setup individual service (create dirs, verify)\n"
	@printf "\n"
	@printf "    $(BOLD)Note:$(RESET) 'init' creates the master config.env file.\n"
	@printf "         'setup' generates component-specific configs (.env files).\n"
	@printf "         '<service>-setup' prepares that service's directories.\n"
	@printf "\n"
	@printf "$(BOLD)Cleanup:$(RESET)\n"
	@printf "    make clean           Stop containers, keep data\n"
	@printf "    make clean-all       $(RED)DANGER$(RESET) Remove everything\n"
	@printf "\n"
	@printf "$(BOLD)Fresh Start (Clear Data):$(RESET)\n"
	@printf "    make <service>-stop  Stop the service first\n"
	@printf "    make <service>-clear Clear all data for that service\n"
	@printf "    make setup           Regenerate configs\n"
	@printf "    make <service>-start Start fresh\n"
	@printf "\n"
	@printf "    Examples:\n"
	@printf "      make monitoring-stop && make monitoring-clear && make setup && make monitoring-start\n"
	@printf "      make orthanc-stop && make orthanc-clear && make setup && make orthanc-start\n"

# =============================================================================
# GLOBAL COMMANDS
# =============================================================================

status:
	@printf "$(BOLD)$(CYAN)═══════════════════════════════════════════════════════════════$(RESET)\n"
	@printf "$(BOLD)$(CYAN)                      SERVICE STATUS                           $(RESET)\n"
	@printf "$(BOLD)$(CYAN)═══════════════════════════════════════════════════════════════$(RESET)\n"
	@printf "\n"
	@printf "$(BOLD)$(GREEN)▸ Orthanc$(RESET)\n"
	@cd orthanc && sudo docker compose ps --format "table {{.Name}}\t{{.Status}}\t{{.Ports}}" 2>/dev/null || printf "  Not running\n"
	@printf "\n"
	@printf "$(BOLD)$(GREEN)▸ Mercure$(RESET)\n"
	@cd /opt/mercure && sudo docker compose ps --format "table {{.Name}}\t{{.Status}}\t{{.Ports}}" 2>/dev/null || printf "  Not running\n"
	@printf "\n"
	@printf "$(BOLD)$(GREEN)▸ Monitoring$(RESET)\n"
	@cd monitoring-v2 && sudo docker compose ps --format "table {{.Name}}\t{{.Status}}\t{{.Ports}}" 2>/dev/null || printf "  Not running\n"
	@printf "\n"
	@printf "$(BOLD)$(GREEN)▸ AI Module$(RESET)\n"
	@sudo docker images stanfordaide/pediatric-leglength --format "  {{.Repository}}:{{.Tag}}  ({{.Size}}, created {{.CreatedSince}})" 2>/dev/null || printf "  Image not built\n"
	@printf "\n"

start-all: mercure-start orthanc-start monitoring-start
	@printf "\n"
	@printf "$(GREEN)✅ All services started!$(RESET)\n"
	@printf "\n"
	@printf "Access points:\n"
	@printf "  Orthanc Dashboard:  http://localhost:9010\n"
	@printf "  Orthanc Web:        http://localhost:9011\n"
	@printf "  OHIF Viewer:        http://localhost:9012\n"
	@printf "  Mercure:            http://localhost:9020\n"
	@printf "  Workflow UI:        http://localhost:9030\n"
	@printf "  Grafana:            http://localhost:9032\n"

stop-all: monitoring-stop orthanc-stop mercure-stop
	@printf "$(YELLOW)All services stopped.$(RESET)\n"

ps:
	@sudo docker ps --filter "name=orthanc" --filter "name=mercure" --filter "name=workflow" --filter "name=grafana" --filter "name=prometheus" --filter "name=monitoring" --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"

urls:
	@printf "$(BOLD)$(CYAN)Service URLs$(RESET)\n"
	@printf "\n"
	@printf "$(GREEN)Orthanc$(RESET)\n"
	@printf "  Dashboard:     http://localhost:9010\n"
	@printf "  Web/API:       http://localhost:9011\n"
	@printf "  OHIF Viewer:   http://localhost:9012\n"
	@printf "  DICOM:         localhost:4242 (C-STORE)\n"
	@printf "\n"
	@printf "$(GREEN)Mercure$(RESET)\n"
	@printf "  Web UI:        http://localhost:9020\n"
	@printf "\n"
	@printf "$(GREEN)Monitoring$(RESET)\n"
	@printf "  Workflow UI:   http://localhost:9030\n"
	@printf "  Grafana:       http://localhost:9032\n"
	@printf "  Prometheus:    http://localhost:9033\n"

# =============================================================================
# ORTHANC - DICOM PACS Server
# =============================================================================

orthanc-start:
	@printf "$(CYAN)Starting Orthanc...$(RESET)\n"
	@cd orthanc && sudo make setup && sudo make start && sudo make seed-modalities
	@printf "$(GREEN)✅ Orthanc started$(RESET)\n"

orthanc-stop:
	@printf "$(YELLOW)Stopping Orthanc...$(RESET)\n"
	@cd orthanc && sudo docker compose down
	@printf "$(YELLOW)Orthanc stopped$(RESET)\n"

orthanc-ps:
	@printf "$(CYAN)Orthanc Containers:$(RESET)\n"
	@cd orthanc && docker compose ps

orthanc-logs:
	@cd orthanc && sudo docker compose logs -f --tail=100

orthanc-setup:
	@printf "$(CYAN)Setting up Orthanc...$(RESET)\n"
	@cd orthanc && make setup
	@printf "$(GREEN)✅ Orthanc setup complete$(RESET)\n"

orthanc-clear:
	@printf "$(YELLOW)Clearing Orthanc data...$(RESET)\n"
	@printf "\n"
	@printf "Checking if Orthanc is stopped...\n"
	@if cd orthanc && docker compose ps 2>/dev/null | grep -q "Up"; then \
		printf "$(RED)❌ ERROR: Orthanc is still running!$(RESET)\n"; \
		printf "   Please run 'make orthanc-stop' first.\n"; \
		exit 1; \
	fi
	@printf "$(GREEN)✅ Orthanc is stopped$(RESET)\n"
	@printf "\n"
	@printf "$(YELLOW)⚠️  This will permanently delete:$(RESET)\n"
	@printf "   - All Docker volumes\n"
	@printf "   - DICOM storage data\n"
	@printf "   - PostgreSQL database data\n"
	@printf "   - Configuration file (.env)\n"
	@printf "\n"
	@read -p "Continue? Type 'yes' to confirm: " confirm && [ "$$confirm" = "yes" ] || exit 1
	@printf "\n"
	@printf "$(YELLOW)🗑️  Removing containers and volumes...$(RESET)\n"
	@cd orthanc && docker compose down -v --remove-orphans 2>/dev/null || true
	@printf "$(YELLOW)🗑️  Clearing DICOM and database storage...$(RESET)\n"
	@cd orthanc && if [ -f .env ]; then \
		. ./.env && \
		if [ -n "$$DICOM_STORAGE" ] && [ -d "$$DICOM_STORAGE" ]; then \
			sudo rm -rf "$$DICOM_STORAGE"/* 2>/dev/null || rm -rf "$$DICOM_STORAGE"/* 2>/dev/null || true; \
			printf "   ✅ Cleared DICOM storage: $$DICOM_STORAGE\n"; \
		fi && \
		if [ -n "$$POSTGRES_STORAGE" ] && [ -d "$$POSTGRES_STORAGE" ]; then \
			sudo rm -rf "$$POSTGRES_STORAGE"/* 2>/dev/null || rm -rf "$$POSTGRES_STORAGE"/* 2>/dev/null || true; \
			printf "   ✅ Cleared PostgreSQL storage: $$POSTGRES_STORAGE\n"; \
		fi; \
	else \
		printf "   ⚠️  .env not found, skipping data directory cleanup\n"; \
	fi
	@printf "$(YELLOW)🗑️  Removing configuration...$(RESET)\n"
	@cd orthanc && rm -f .env 2>/dev/null || true
	@printf "\n"
	@printf "$(GREEN)✅ Orthanc cleared$(RESET)\n"
	@printf "\n"
	@printf "Next steps:\n"
	@printf "  1. make setup          (regenerate configs)\n"
	@printf "  2. make orthanc-start\n"

# =============================================================================
# MERCURE - AI Job Orchestrator
# =============================================================================

mercure-start:
	@printf "$(CYAN)Starting Mercure...$(RESET)\n"
	@if [ -d "/opt/mercure" ]; then \
		printf "$(CYAN)Ensuring data directories exist with correct permissions...$(RESET)\n"; \
		if id -u mercure >/dev/null 2>&1; then \
			MERCURE_UID=$$(id -u mercure); \
			MERCURE_GID=$$(id -g mercure); \
		else \
			MERCURE_UID=1000; \
			MERCURE_GID=1000; \
		fi; \
		sudo mkdir -p /opt/mercure/data/{incoming,studies,outgoing,success,error,discard,processing,jobs}; \
		sudo mkdir -p /opt/mercure/persistence; \
		sudo chown -R $$MERCURE_UID:$$MERCURE_GID /opt/mercure/data /opt/mercure/persistence 2>/dev/null || \
			sudo chmod -R 777 /opt/mercure/data /opt/mercure/persistence; \
		cd /opt/mercure && sudo docker compose up -d; \
	else \
		chmod +x scripts/install-mercure.sh && ./scripts/install-mercure.sh -y; \
	fi
	@printf "$(GREEN)✅ Mercure started$(RESET)\n"

mercure-stop:
	@printf "$(YELLOW)Stopping Mercure...$(RESET)\n"
	@cd /opt/mercure && sudo docker compose down 2>/dev/null || printf "Mercure not running\n"
	@printf "$(YELLOW)Mercure stopped$(RESET)\n"

mercure-ps:
	@printf "$(CYAN)Mercure Containers:$(RESET)\n"
	@if [ -d "/opt/mercure" ]; then \
		cd /opt/mercure && sudo docker compose ps; \
	else \
		printf "  Mercure not installed\n"; \
	fi

mercure-logs:
	@cd /opt/mercure && sudo docker compose logs -f --tail=100

mercure-setup:
	@printf "$(CYAN)Checking Mercure installation...$(RESET)\n"
	@if [ ! -d "/opt/mercure" ]; then \
		printf "$(YELLOW)Mercure not installed. Installing...$(RESET)\n"; \
		chmod +x scripts/install-mercure.sh && ./scripts/install-mercure.sh -y; \
	else \
		printf "$(GREEN)✅ Mercure is installed at /opt/mercure$(RESET)\n"; \
		printf "$(CYAN)Verifying configuration...$(RESET)\n"; \
		cd /opt/mercure && sudo docker compose config > /dev/null 2>&1 && \
			printf "$(GREEN)✅ Configuration valid$(RESET)\n" || \
			printf "$(YELLOW)⚠️  Configuration may need attention$(RESET)\n"; \
	fi

mercure-clear:
	@printf "$(YELLOW)Clearing Mercure data...$(RESET)\n"
	@printf "\n"
	@if [ ! -d "/opt/mercure" ]; then \
		printf "$(YELLOW)Mercure not installed. Nothing to clear.$(RESET)\n"; \
		exit 0; \
	fi
	@printf "Checking if Mercure is stopped...\n"
	@if cd /opt/mercure && sudo docker compose ps 2>/dev/null | grep -q "Up"; then \
		printf "$(RED)❌ ERROR: Mercure is still running!$(RESET)\n"; \
		printf "   Please run 'make mercure-stop' first.\n"; \
		exit 1; \
	fi
	@printf "$(GREEN)✅ Mercure is stopped$(RESET)\n"
	@printf "\n"
	@printf "$(YELLOW)⚠️  This will permanently delete:$(RESET)\n"
	@printf "   - All Docker volumes\n"
	@printf "   - Mercure database and job data\n"
	@printf "   - All processed jobs history\n"
	@printf "\n"
	@read -p "Continue? Type 'yes' to confirm: " confirm && [ "$$confirm" = "yes" ] || exit 1
	@printf "\n"
	@printf "$(YELLOW)🗑️  Removing containers and volumes...$(RESET)\n"
	@cd /opt/mercure && sudo docker compose down -v --remove-orphans 2>/dev/null || true
	@printf "$(YELLOW)🗑️  Clearing Mercure data directories...$(RESET)\n"
	@sudo rm -rf /opt/mercure/data/* 2>/dev/null || true
	@sudo rm -rf /opt/mercure/db/* 2>/dev/null || true
	@printf "\n"
	@printf "$(GREEN)✅ Mercure cleared$(RESET)\n"
	@printf "\n"
	@printf "Next steps:\n"
	@printf "  1. make setup          (regenerate configs if needed)\n"
	@printf "  2. make mercure-start\n"

# =============================================================================
# MONITORING - Metrics Collection (Grafana, Prometheus, Graphite)
# =============================================================================

monitoring-start:
	@printf "$(CYAN)Starting Monitoring stack...$(RESET)\n"
	@if [ ! -f "monitoring-v2/config/prometheus/prometheus.yml" ]; then \
		printf "$(RED)❌ ERROR: prometheus.yml not found!$(RESET)\n"; \
		printf "   Run 'make setup' first to generate configs.\n"; \
		exit 1; \
	fi
	@cd monitoring-v2 && make start
	@printf "$(GREEN)✅ Monitoring started$(RESET)\n"

monitoring-stop:
	@printf "$(YELLOW)Stopping Monitoring stack...$(RESET)\n"
	@cd monitoring-v2 && make stop
	@printf "$(YELLOW)Monitoring stopped$(RESET)\n"

monitoring-ps:
	@printf "$(CYAN)Monitoring Containers:$(RESET)\n"
	@cd monitoring-v2 && docker compose ps

monitoring-logs:
	@cd monitoring-v2 && make logs

monitoring-clear:
	@printf "$(YELLOW)Clearing Monitoring data...$(RESET)\n"
	@cd monitoring-v2 && make clear
	@printf "$(GREEN)✅ Monitoring cleared$(RESET)\n"
	@printf "\n"
	@printf "Next steps:\n"
	@printf "  1. make setup          (regenerate configs)\n"
	@printf "  2. make monitoring-start\n"

monitoring-setup:
	@printf "$(CYAN)Setting up Monitoring...$(RESET)\n"
	@cd monitoring-v2 && make setup
	@printf "$(GREEN)✅ Monitoring setup complete$(RESET)\n"

# =============================================================================
# AI MODULE - Docker Image (Build Artifact)
# =============================================================================

AI_IMAGE := stanfordaide/pediatric-leglength
AI_TAG   := latest

ai-build:
	@printf "$(CYAN)Building AI module...$(RESET)\n"
	@cd mercure-pediatric-leglength && docker build -t $(AI_IMAGE):$(AI_TAG) .
	@printf "$(GREEN)✅ AI module built: $(AI_IMAGE):$(AI_TAG)$(RESET)\n"

ai-test:
	@printf "$(CYAN)Testing AI module...$(RESET)\n"
	@cd mercure-pediatric-leglength && python test_model_loading.py
	@printf "$(GREEN)✅ AI module tests passed$(RESET)\n"

ai-push:
	@printf "$(CYAN)Pushing AI module to registry...$(RESET)\n"
	@docker push $(AI_IMAGE):$(AI_TAG)
	@printf "$(GREEN)✅ Pushed $(AI_IMAGE):$(AI_TAG)$(RESET)\n"

ai-clean:
	@printf "$(YELLOW)Removing old AI images...$(RESET)\n"
	@docker images $(AI_IMAGE) -q | xargs -r docker rmi -f 2>/dev/null || true
	@docker image prune -f --filter "label=maintainer=stanfordaide"
	@printf "$(YELLOW)AI images cleaned$(RESET)\n"

ai-info:
	@printf "$(CYAN)AI Module Info:$(RESET)\n"
	@docker images $(AI_IMAGE) --format "table {{.Repository}}\t{{.Tag}}\t{{.Size}}\t{{.CreatedSince}}"
	@printf "\n"
	@printf "$(CYAN)Models in registry.json:$(RESET)\n"
	@cat mercure-pediatric-leglength/registry.json | jq -r 'keys[]' | while read m; do printf "  • $$m\n"; done

# =============================================================================
# SETUP
# =============================================================================

init:
	@if [ -f config.env ]; then \
		printf "$(YELLOW)config.env already exists.$(RESET)\n"; \
		printf "Edit it or delete to recreate from template.\n"; \
	else \
		cp config.env.template config.env; \
		chmod 600 config.env; \
		printf "$(GREEN)✅ Created config.env$(RESET)\n"; \
		printf "\n"; \
		printf "$(BOLD)Next steps:$(RESET)\n"; \
		printf "  1. Edit config.env with your passwords\n"; \
		printf "  2. Run 'make setup' to generate component configs\n"; \
	fi

setup: setup-config

setup-config:
	@if [ ! -f config.env ]; then \
		printf "$(RED)ERROR: config.env not found!$(RESET)\n"; \
		printf "Run 'make init' first, then edit config.env\n"; \
		exit 1; \
	fi
	@./scripts/setup-config.sh
	@if [ -f mercure/config-generated/mercure.json ] && [ -d /opt/mercure/config ]; then \
		printf "$(CYAN)Copying mercure.json to /opt/mercure/config/...$(RESET)\n"; \
		sudo cp mercure/config-generated/mercure.json /opt/mercure/config/mercure.json && \
		sudo chown mercure:mercure /opt/mercure/config/mercure.json 2>/dev/null || \
		sudo chmod 644 /opt/mercure/config/mercure.json; \
		printf "$(GREEN)✅ mercure.json copied to /opt/mercure/config/$(RESET)\n"; \
	fi
	@printf "$(GREEN)✅ All configs generated from config.env$(RESET)\n"

# =============================================================================
# CLEANUP
# =============================================================================

clean:
	@printf "$(YELLOW)This will stop all containers (data preserved).$(RESET)\n"
	@read -p "Continue? [y/N] " confirm && [ "$$confirm" = "y" ] || exit 1
	@cd orthanc && docker compose down 2>/dev/null || true
	@cd /opt/mercure && sudo docker compose down 2>/dev/null || true
	@cd monitoring-v2 && docker compose down 2>/dev/null || true
	@printf "$(GREEN)✅ All containers stopped. Data preserved.$(RESET)\n"

clean-all:
	@printf "$(RED)╔══════════════════════════════════════════════════════════════╗$(RESET)\n"
	@printf "$(RED)║  ⚠️  DANGER: This will PERMANENTLY DELETE everything:        ║$(RESET)\n"
	@printf "$(RED)║                                                              ║$(RESET)\n"
	@printf "$(RED)║    • All containers, images, and volumes                    ║$(RESET)\n"
	@printf "$(RED)║    • Mercure installation (/opt/mercure)                    ║$(RESET)\n"
	@printf "$(RED)║    • Orthanc data and PostgreSQL                            ║$(RESET)\n"
	@printf "$(RED)║    • All generated config files                             ║$(RESET)\n"
	@printf "$(RED)╚══════════════════════════════════════════════════════════════╝$(RESET)\n"
	@printf "\n"
	@read -p "Type 'DELETE' to confirm: " confirm && [ "$$confirm" = "DELETE" ] || exit 1
	@printf "\n"
	@printf "$(YELLOW)Stopping services...$(RESET)\n"
	@cd orthanc && sudo docker compose down -v 2>/dev/null || true
	@cd /opt/mercure && sudo docker compose down -v 2>/dev/null || true
	@cd monitoring-v2 && sudo docker compose down -v 2>/dev/null || true
	@printf "$(YELLOW)Removing Mercure...$(RESET)\n"
	@sudo rm -rf /opt/mercure
	@printf "$(YELLOW)Removing Orthanc data...$(RESET)\n"
	@sudo rm -rf /opt/orthanc
	@sudo rm -rf /home/orthanc/orthanc-storage
	@sudo rm -rf /home/orthanc/postgres-data
	@printf "$(YELLOW)Removing generated configs...$(RESET)\n"
	@rm -f orthanc/.env orthanc/config/orthanc.json
	@rm -f monitoring-v2/.env
	@rm -rf mercure/config-generated/
	@rm -f config.env
	@printf "$(YELLOW)Docker cleanup...$(RESET)\n"
	@sudo docker stop $$(sudo docker ps -aq) 2>/dev/null || true
	@sudo docker rm $$(sudo docker ps -aq) 2>/dev/null || true
	@sudo docker volume rm $$(sudo docker volume ls -q) 2>/dev/null || true
	@sudo docker image prune -af
	@sudo docker builder prune -af
	@sudo docker network prune -f
	@printf "\n"
	@printf "$(GREEN)✅ Complete cleanup done!$(RESET)\n"
	@printf "\n"
	@printf "To start fresh:\n"
	@printf "  make init\n"
	@printf "  nano config.env\n"
	@printf "  make setup\n"
	@printf "  make start-all\n"
	@printf "  make ai-build\n"

.PHONY: workflow-sync
workflow-sync:
	@printf "$(BOLD)$(CYAN)Syncing workflows from Mercure Bookkeeper...$(RESET)\n"
	@curl -X POST http://localhost:9031/workflows/sync | jq .
	@printf "\n"
