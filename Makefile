# Pediatric Leg Length AI - Deployment Makefile
# Master orchestration for all components
#
# PATTERN:
#   Services (orthanc, mercure, monitoring): start, stop, restart, status, logs, shell
#   Build artifacts (ai): build, test, push, clean, info

.PHONY: help status start-all stop-all restart-all \
        orthanc-start orthanc-stop orthanc-restart orthanc-status orthanc-logs orthanc-shell orthanc-validate \
        mercure-start mercure-stop mercure-restart mercure-status mercure-logs mercure-shell \
        monitoring-start monitoring-stop monitoring-restart monitoring-status monitoring-logs \
        ai-build ai-test ai-push ai-clean ai-info \
        init setup setup-config clean clean-all ps

# Colors
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
	@echo "$(BOLD)$(CYAN)Pediatric Leg Length AI - Deployment$(RESET)"
	@echo ""
	@echo "$(BOLD)Global Commands:$(RESET)"
	@echo "  make status            Show status of all services"
	@echo "  make start-all         Start all components"
	@echo "  make stop-all          Stop all components"
	@echo "  make restart-all       Restart all components"
	@echo "  make ps                Show running containers"
	@echo ""
	@echo "$(BOLD)Services (start/stop/restart/status/logs/shell):$(RESET)"
	@echo ""
	@echo "  $(GREEN)Orthanc$(RESET) - DICOM PACS Server"
	@echo "    make orthanc-start   Start Orthanc"
	@echo "    make orthanc-stop    Stop Orthanc"
	@echo "    make orthanc-restart Restart Orthanc"
	@echo "    make orthanc-status  Check Orthanc health"
	@echo "    make orthanc-logs    View Orthanc logs"
	@echo "    make orthanc-shell   Shell into Orthanc container"
	@echo "    make orthanc-validate Check Orthanc config"
	@echo ""
	@echo "  $(GREEN)Mercure$(RESET) - AI Job Orchestrator"
	@echo "    make mercure-start   Start Mercure"
	@echo "    make mercure-stop    Stop Mercure"
	@echo "    make mercure-restart Restart Mercure"
	@echo "    make mercure-status  Check Mercure health"
	@echo "    make mercure-logs    View Mercure logs"
	@echo "    make mercure-shell   Shell into Mercure container"
	@echo ""
	@echo "  $(GREEN)Monitoring$(RESET) - Grafana, Prometheus, Workflow UI"
	@echo "    make monitoring-start   Start monitoring stack"
	@echo "    make monitoring-stop    Stop monitoring stack"
	@echo "    make monitoring-restart Restart monitoring stack"
	@echo "    make monitoring-status  Check monitoring health"
	@echo "    make monitoring-logs    View monitoring logs"
	@echo ""
	@echo "$(BOLD)AI Module (build/test/push/clean/info):$(RESET)"
	@echo "    make ai-build        Build Docker image"
	@echo "    make ai-test         Test model loading"
	@echo "    make ai-push         Push to registry"
	@echo "    make ai-clean        Remove old images"
	@echo "    make ai-info         Show image info"
	@echo ""
	@echo "$(BOLD)Setup (run in order):$(RESET)"
	@echo "    make init            Create config.env from template"
	@echo "    nano config.env      Edit passwords and paths"
	@echo "    make setup           Generate all component configs"
	@echo ""
	@echo "$(BOLD)Cleanup:$(RESET)"
	@echo "    make clean           Stop containers, keep data"
	@echo "    make clean-all       $(RED)DANGER$(RESET) Remove everything"

# =============================================================================
# GLOBAL COMMANDS
# =============================================================================

status:
	@echo "$(BOLD)$(CYAN)═══════════════════════════════════════════════════════════════$(RESET)"
	@echo "$(BOLD)$(CYAN)                      SERVICE STATUS                           $(RESET)"
	@echo "$(BOLD)$(CYAN)═══════════════════════════════════════════════════════════════$(RESET)"
	@echo ""
	@echo "$(BOLD)$(GREEN)▸ Orthanc$(RESET)"
	@cd orthanc && docker compose ps --format "table {{.Name}}\t{{.Status}}\t{{.Ports}}" 2>/dev/null || echo "  Not running"
	@echo ""
	@echo "$(BOLD)$(GREEN)▸ Mercure$(RESET)"
	@cd /opt/mercure && docker compose ps --format "table {{.Name}}\t{{.Status}}\t{{.Ports}}" 2>/dev/null || echo "  Not running"
	@echo ""
	@echo "$(BOLD)$(GREEN)▸ Monitoring$(RESET)"
	@cd monitoring && docker compose ps --format "table {{.Name}}\t{{.Status}}\t{{.Ports}}" 2>/dev/null || echo "  Not running"
	@echo ""
	@echo "$(BOLD)$(GREEN)▸ AI Module$(RESET)"
	@docker images stanfordaide/pediatric-leglength --format "  {{.Repository}}:{{.Tag}}  ({{.Size}}, created {{.CreatedSince}})" 2>/dev/null || echo "  Image not built"
	@echo ""

start-all: monitoring-start orthanc-start mercure-start
	@echo ""
	@echo "$(GREEN)✅ All services started!$(RESET)"
	@echo ""
	@echo "Access points:"
	@echo "  Orthanc Dashboard:  http://localhost:9010"
	@echo "  Orthanc Web:        http://localhost:9011"
	@echo "  OHIF Viewer:        http://localhost:9012"
	@echo "  Mercure:            http://localhost:9020"
	@echo "  Workflow UI:        http://localhost:9030"
	@echo "  Grafana:            http://localhost:9032"

stop-all: mercure-stop orthanc-stop monitoring-stop
	@echo "$(YELLOW)All services stopped.$(RESET)"

restart-all: stop-all start-all

ps:
	@docker ps --filter "name=orthanc" --filter "name=mercure" --filter "name=workflow" --filter "name=grafana" --filter "name=prometheus" --filter "name=monitoring" --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"

# =============================================================================
# ORTHANC - DICOM PACS Server
# =============================================================================

orthanc-start:
	@echo "$(CYAN)Starting Orthanc...$(RESET)"
	@cd orthanc && sudo make setup && sudo make start && sudo make seed-modalities
	@echo "$(GREEN)✅ Orthanc started$(RESET)"

orthanc-stop:
	@echo "$(YELLOW)Stopping Orthanc...$(RESET)"
	@cd orthanc && sudo docker compose down
	@echo "$(YELLOW)Orthanc stopped$(RESET)"

orthanc-restart: orthanc-stop orthanc-start

orthanc-status:
	@echo "$(CYAN)Orthanc Status:$(RESET)"
	@cd orthanc && docker compose ps
	@echo ""
	@echo "$(CYAN)Health Check:$(RESET)"
	@curl -sf http://localhost:9011/system 2>/dev/null | jq -r '"  Version: \(.Version)\n  DICOM AET: \(.DicomAet)\n  Storage: \(.StorageSize) bytes"' || echo "  $(RED)Not responding$(RESET)"

orthanc-logs:
	@cd orthanc && docker compose logs -f --tail=100

orthanc-shell:
	@cd orthanc && docker compose exec orthanc bash

orthanc-validate:
	@echo "$(CYAN)Validating Orthanc configuration...$(RESET)"
	@cd orthanc && make validate

# =============================================================================
# MERCURE - AI Job Orchestrator
# =============================================================================

mercure-start:
	@echo "$(CYAN)Starting Mercure...$(RESET)"
	@chmod +x scripts/install-mercure.sh
	@./scripts/install-mercure.sh -y
	@echo "$(GREEN)✅ Mercure started$(RESET)"

mercure-stop:
	@echo "$(YELLOW)Stopping Mercure...$(RESET)"
	@cd /opt/mercure && sudo docker compose down 2>/dev/null || echo "Mercure not running"
	@echo "$(YELLOW)Mercure stopped$(RESET)"

mercure-restart: mercure-stop mercure-start

mercure-status:
	@echo "$(CYAN)Mercure Status:$(RESET)"
	@cd /opt/mercure && docker compose ps 2>/dev/null || echo "  Not running"
	@echo ""
	@echo "$(CYAN)Health Check:$(RESET)"
	@curl -sf http://localhost:9020/api/status 2>/dev/null && echo "  $(GREEN)Responding$(RESET)" || echo "  $(RED)Not responding$(RESET)"

mercure-logs:
	@cd /opt/mercure && docker compose logs -f --tail=100

mercure-shell:
	@cd /opt/mercure && docker compose exec mercure_ui bash

# =============================================================================
# MONITORING - Grafana, Prometheus, Workflow UI
# =============================================================================

monitoring-start:
	@echo "$(CYAN)Starting Monitoring stack...$(RESET)"
	@cd monitoring && docker compose up -d
	@echo "$(GREEN)✅ Monitoring started$(RESET)"

monitoring-stop:
	@echo "$(YELLOW)Stopping Monitoring stack...$(RESET)"
	@cd monitoring && docker compose down
	@echo "$(YELLOW)Monitoring stopped$(RESET)"

monitoring-restart: monitoring-stop monitoring-start

monitoring-status:
	@echo "$(CYAN)Monitoring Status:$(RESET)"
	@cd monitoring && docker compose ps
	@echo ""
	@echo "$(CYAN)Service Health:$(RESET)"
	@curl -sf http://localhost:9032/api/health 2>/dev/null && echo "  Grafana:    $(GREEN)OK$(RESET)" || echo "  Grafana:    $(RED)DOWN$(RESET)"
	@curl -sf http://localhost:9033/-/healthy 2>/dev/null && echo "  Prometheus: $(GREEN)OK$(RESET)" || echo "  Prometheus: $(RED)DOWN$(RESET)"
	@curl -sf http://localhost:9031/health 2>/dev/null && echo "  Workflow API: $(GREEN)OK$(RESET)" || echo "  Workflow API: $(RED)DOWN$(RESET)"

monitoring-logs:
	@cd monitoring && docker compose logs -f --tail=100

# =============================================================================
# AI MODULE - Docker Image (Build Artifact)
# =============================================================================

AI_IMAGE := stanfordaide/pediatric-leglength
AI_TAG   := latest

ai-build:
	@echo "$(CYAN)Building AI module...$(RESET)"
	@cd mercure-pediatric-leglength && docker build -t $(AI_IMAGE):$(AI_TAG) .
	@echo "$(GREEN)✅ AI module built: $(AI_IMAGE):$(AI_TAG)$(RESET)"

ai-test:
	@echo "$(CYAN)Testing AI module...$(RESET)"
	@cd mercure-pediatric-leglength && python test_model_loading.py
	@echo "$(GREEN)✅ AI module tests passed$(RESET)"

ai-push:
	@echo "$(CYAN)Pushing AI module to registry...$(RESET)"
	@docker push $(AI_IMAGE):$(AI_TAG)
	@echo "$(GREEN)✅ Pushed $(AI_IMAGE):$(AI_TAG)$(RESET)"

ai-clean:
	@echo "$(YELLOW)Removing old AI images...$(RESET)"
	@docker images $(AI_IMAGE) -q | xargs -r docker rmi -f 2>/dev/null || true
	@docker image prune -f --filter "label=maintainer=stanfordaide"
	@echo "$(YELLOW)AI images cleaned$(RESET)"

ai-info:
	@echo "$(CYAN)AI Module Info:$(RESET)"
	@docker images $(AI_IMAGE) --format "table {{.Repository}}\t{{.Tag}}\t{{.Size}}\t{{.CreatedSince}}"
	@echo ""
	@echo "$(CYAN)Models in registry.json:$(RESET)"
	@cat mercure-pediatric-leglength/registry.json | jq -r 'keys[]' | while read m; do echo "  • $$m"; done

# =============================================================================
# SETUP
# =============================================================================

init:
	@if [ -f config.env ]; then \
		echo "$(YELLOW)config.env already exists.$(RESET)"; \
		echo "Edit it or delete to recreate from template."; \
	else \
		cp config.env.template config.env; \
		chmod 600 config.env; \
		echo "$(GREEN)✅ Created config.env$(RESET)"; \
		echo ""; \
		echo "$(BOLD)Next steps:$(RESET)"; \
		echo "  1. Edit config.env with your passwords"; \
		echo "  2. Run 'make setup' to generate component configs"; \
	fi

setup: setup-config

setup-config:
	@if [ ! -f config.env ]; then \
		echo "$(RED)ERROR: config.env not found!$(RESET)"; \
		echo "Run 'make init' first, then edit config.env"; \
		exit 1; \
	fi
	@./scripts/setup-config.sh
	@echo "$(GREEN)✅ All configs generated from config.env$(RESET)"

# =============================================================================
# CLEANUP
# =============================================================================

clean:
	@echo "$(YELLOW)This will stop all containers (data preserved).$(RESET)"
	@read -p "Continue? [y/N] " confirm && [ "$$confirm" = "y" ] || exit 1
	@cd orthanc && docker compose down 2>/dev/null || true
	@cd /opt/mercure && sudo docker compose down 2>/dev/null || true
	@cd monitoring && docker compose down 2>/dev/null || true
	@echo "$(GREEN)✅ All containers stopped. Data preserved.$(RESET)"

clean-all:
	@echo "$(RED)╔══════════════════════════════════════════════════════════════╗$(RESET)"
	@echo "$(RED)║  ⚠️  DANGER: This will PERMANENTLY DELETE everything:        ║$(RESET)"
	@echo "$(RED)║                                                              ║$(RESET)"
	@echo "$(RED)║    • All containers, images, and volumes                    ║$(RESET)"
	@echo "$(RED)║    • Mercure installation (/opt/mercure)                    ║$(RESET)"
	@echo "$(RED)║    • Orthanc data and PostgreSQL                            ║$(RESET)"
	@echo "$(RED)║    • All generated config files                             ║$(RESET)"
	@echo "$(RED)╚══════════════════════════════════════════════════════════════╝$(RESET)"
	@echo ""
	@read -p "Type 'DELETE' to confirm: " confirm && [ "$$confirm" = "DELETE" ] || exit 1
	@echo ""
	@echo "$(YELLOW)Stopping services...$(RESET)"
	@cd orthanc && sudo docker compose down -v 2>/dev/null || true
	@cd /opt/mercure && sudo docker compose down -v 2>/dev/null || true
	@cd monitoring && sudo docker compose down -v 2>/dev/null || true
	@echo "$(YELLOW)Removing Mercure...$(RESET)"
	@sudo rm -rf /opt/mercure
	@echo "$(YELLOW)Removing Orthanc data...$(RESET)"
	@sudo rm -rf /opt/orthanc
	@sudo rm -rf /home/orthanc/orthanc-storage
	@sudo rm -rf /home/orthanc/postgres-data
	@echo "$(YELLOW)Removing generated configs...$(RESET)"
	@rm -f orthanc/.env orthanc/config/orthanc.json
	@rm -f monitoring/.env
	@rm -rf mercure/config-generated/
	@rm -f config.env
	@echo "$(YELLOW)Docker cleanup...$(RESET)"
	@sudo docker stop $$(sudo docker ps -aq) 2>/dev/null || true
	@sudo docker rm $$(sudo docker ps -aq) 2>/dev/null || true
	@sudo docker volume rm $$(sudo docker volume ls -q) 2>/dev/null || true
	@sudo docker image prune -af
	@sudo docker builder prune -af
	@sudo docker network prune -f
	@echo ""
	@echo "$(GREEN)✅ Complete cleanup done!$(RESET)"
	@echo ""
	@echo "To start fresh:"
	@echo "  make init"
	@echo "  nano config.env"
	@echo "  make setup"
	@echo "  make start-all"
	@echo "  make ai-build"
