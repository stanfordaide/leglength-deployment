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
	@printf "  make start-all         Start all components\n"
	@printf "  make stop-all          Stop all components\n"
	@printf "  make restart-all       Restart all components\n"
	@printf "  make ps                Show running containers\n"
	@printf "\n"
	@printf "$(BOLD)Services (start/stop/restart/status/logs/shell):$(RESET)\n"
	@printf "\n"
	@printf "  $(GREEN)Orthanc$(RESET) - DICOM PACS Server\n"
	@printf "    make orthanc-start   Start Orthanc\n"
	@printf "    make orthanc-stop    Stop Orthanc\n"
	@printf "    make orthanc-restart Restart Orthanc\n"
	@printf "    make orthanc-status  Check Orthanc health\n"
	@printf "    make orthanc-logs    View Orthanc logs\n"
	@printf "    make orthanc-shell   Shell into Orthanc container\n"
	@printf "    make orthanc-validate Check Orthanc config\n"
	@printf "\n"
	@printf "  $(GREEN)Mercure$(RESET) - AI Job Orchestrator\n"
	@printf "    make mercure-start   Start Mercure\n"
	@printf "    make mercure-stop    Stop Mercure\n"
	@printf "    make mercure-restart Restart Mercure\n"
	@printf "    make mercure-status  Check Mercure health\n"
	@printf "    make mercure-logs    View Mercure logs\n"
	@printf "    make mercure-shell   Shell into Mercure container\n"
	@printf "\n"
	@printf "  $(GREEN)Monitoring$(RESET) - Grafana, Prometheus, Workflow UI\n"
	@printf "    make monitoring-start   Start monitoring stack\n"
	@printf "    make monitoring-stop    Stop monitoring stack\n"
	@printf "    make monitoring-restart Restart monitoring stack\n"
	@printf "    make monitoring-status  Check monitoring health\n"
	@printf "    make monitoring-logs    View monitoring logs\n"
	@printf "\n"
	@printf "$(BOLD)AI Module (build/test/push/clean/info):$(RESET)\n"
	@printf "    make ai-build        Build Docker image\n"
	@printf "    make ai-test         Test model loading\n"
	@printf "    make ai-push         Push to registry\n"
	@printf "    make ai-clean        Remove old images\n"
	@printf "    make ai-info         Show image info\n"
	@printf "\n"
	@printf "$(BOLD)Setup (run in order):$(RESET)\n"
	@printf "    make init            Create config.env from template\n"
	@printf "    nano config.env      Edit passwords and paths\n"
	@printf "    make setup           Generate all component configs\n"
	@printf "\n"
	@printf "$(BOLD)Cleanup:$(RESET)\n"
	@printf "    make clean           Stop containers, keep data\n"
	@printf "    make clean-all       $(RED)DANGER$(RESET) Remove everything\n"

# =============================================================================
# GLOBAL COMMANDS
# =============================================================================

status:
	@printf "$(BOLD)$(CYAN)═══════════════════════════════════════════════════════════════$(RESET)\n"
	@printf "$(BOLD)$(CYAN)                      SERVICE STATUS                           $(RESET)\n"
	@printf "$(BOLD)$(CYAN)═══════════════════════════════════════════════════════════════$(RESET)\n"
	@printf "\n"
	@printf "$(BOLD)$(GREEN)▸ Orthanc$(RESET)\n"
	@cd orthanc && docker compose ps --format "table {{.Name}}\t{{.Status}}\t{{.Ports}}" 2>/dev/null || printf "  Not running\n"
	@printf "\n"
	@printf "$(BOLD)$(GREEN)▸ Mercure$(RESET)\n"
	@cd /opt/mercure && docker compose ps --format "table {{.Name}}\t{{.Status}}\t{{.Ports}}" 2>/dev/null || printf "  Not running\n"
	@printf "\n"
	@printf "$(BOLD)$(GREEN)▸ Monitoring$(RESET)\n"
	@cd monitoring && docker compose ps --format "table {{.Name}}\t{{.Status}}\t{{.Ports}}" 2>/dev/null || printf "  Not running\n"
	@printf "\n"
	@printf "$(BOLD)$(GREEN)▸ AI Module$(RESET)\n"
	@docker images stanfordaide/pediatric-leglength --format "  {{.Repository}}:{{.Tag}}  ({{.Size}}, created {{.CreatedSince}})" 2>/dev/null || printf "  Image not built\n"
	@printf "\n"

start-all: monitoring-start orthanc-start mercure-start
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

stop-all: mercure-stop orthanc-stop monitoring-stop
	@printf "$(YELLOW)All services stopped.$(RESET)\n"

restart-all: stop-all start-all

ps:
	@docker ps --filter "name=orthanc" --filter "name=mercure" --filter "name=workflow" --filter "name=grafana" --filter "name=prometheus" --filter "name=monitoring" --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"

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

orthanc-restart: orthanc-stop orthanc-start

orthanc-status:
	@printf "$(CYAN)Orthanc Status:$(RESET)\n"
	@cd orthanc && docker compose ps
	@printf "\n"
	@printf "$(CYAN)Health Check:$(RESET)\n"
	@curl -sf http://localhost:9011/system 2>/dev/null | jq -r '"  Version: \(.Version)\n  DICOM AET: \(.DicomAet)\n  Storage: \(.StorageSize) bytes"' || printf "  $(RED)Not responding$(RESET)\n"

orthanc-logs:
	@cd orthanc && docker compose logs -f --tail=100

orthanc-shell:
	@cd orthanc && docker compose exec orthanc bash

orthanc-validate:
	@printf "$(CYAN)Validating Orthanc configuration...$(RESET)\n"
	@cd orthanc && make validate

# =============================================================================
# MERCURE - AI Job Orchestrator
# =============================================================================

mercure-start:
	@printf "$(CYAN)Starting Mercure...$(RESET)\n"
	@chmod +x scripts/install-mercure.sh
	@./scripts/install-mercure.sh -y
	@printf "$(GREEN)✅ Mercure started$(RESET)\n"

mercure-stop:
	@printf "$(YELLOW)Stopping Mercure...$(RESET)\n"
	@cd /opt/mercure && sudo docker compose down 2>/dev/null || printf "Mercure not running\n"
	@printf "$(YELLOW)Mercure stopped$(RESET)\n"

mercure-restart: mercure-stop mercure-start

mercure-status:
	@printf "$(CYAN)Mercure Status:$(RESET)\n"
	@cd /opt/mercure && docker compose ps 2>/dev/null || printf "  Not running\n"
	@printf "\n"
	@printf "$(CYAN)Health Check:$(RESET)\n"
	@curl -sf http://localhost:9020/api/status 2>/dev/null && printf "  $(GREEN)Responding$(RESET)\n" || printf "  $(RED)Not responding$(RESET)\n"

mercure-logs:
	@cd /opt/mercure && docker compose logs -f --tail=100

mercure-shell:
	@cd /opt/mercure && docker compose exec mercure_ui bash

# =============================================================================
# MONITORING - Grafana, Prometheus, Workflow UI
# =============================================================================

monitoring-start:
	@printf "$(CYAN)Starting Monitoring stack...$(RESET)\n"
	@cd monitoring && docker compose up -d
	@printf "$(GREEN)✅ Monitoring started$(RESET)\n"

monitoring-stop:
	@printf "$(YELLOW)Stopping Monitoring stack...$(RESET)\n"
	@cd monitoring && docker compose down
	@printf "$(YELLOW)Monitoring stopped$(RESET)\n"

monitoring-restart: monitoring-stop monitoring-start

monitoring-status:
	@printf "$(CYAN)Monitoring Status:$(RESET)\n"
	@cd monitoring && docker compose ps
	@printf "\n"
	@printf "$(CYAN)Service Health:$(RESET)\n"
	@curl -sf http://localhost:9032/api/health 2>/dev/null && printf "  Grafana:    $(GREEN)OK$(RESET)\n" || printf "  Grafana:    $(RED)DOWN$(RESET)\n"
	@curl -sf http://localhost:9033/-/healthy 2>/dev/null && printf "  Prometheus: $(GREEN)OK$(RESET)\n" || printf "  Prometheus: $(RED)DOWN$(RESET)\n"
	@curl -sf http://localhost:9031/health 2>/dev/null && printf "  Workflow API: $(GREEN)OK$(RESET)\n" || printf "  Workflow API: $(RED)DOWN$(RESET)\n"

monitoring-logs:
	@cd monitoring && docker compose logs -f --tail=100

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
	@printf "$(GREEN)✅ All configs generated from config.env$(RESET)\n"

# =============================================================================
# CLEANUP
# =============================================================================

clean:
	@printf "$(YELLOW)This will stop all containers (data preserved).$(RESET)\n"
	@read -p "Continue? [y/N] " confirm && [ "$$confirm" = "y" ] || exit 1
	@cd orthanc && docker compose down 2>/dev/null || true
	@cd /opt/mercure && sudo docker compose down 2>/dev/null || true
	@cd monitoring && docker compose down 2>/dev/null || true
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
	@cd monitoring && sudo docker compose down -v 2>/dev/null || true
	@printf "$(YELLOW)Removing Mercure...$(RESET)\n"
	@sudo rm -rf /opt/mercure
	@printf "$(YELLOW)Removing Orthanc data...$(RESET)\n"
	@sudo rm -rf /opt/orthanc
	@sudo rm -rf /home/orthanc/orthanc-storage
	@sudo rm -rf /home/orthanc/postgres-data
	@printf "$(YELLOW)Removing generated configs...$(RESET)\n"
	@rm -f orthanc/.env orthanc/config/orthanc.json
	@rm -f monitoring/.env
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
