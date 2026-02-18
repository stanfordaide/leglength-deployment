# Monitoring v2 - Makefile
# Lightweight metrics collection and visualization

.PHONY: help setup start stop restart logs status clean build

# Default target
help:
	@echo "Monitoring v2 - Lightweight Metrics Collection"
	@echo ""
	@echo "Usage: make [target]"
	@echo ""
	@echo "Targets:"
	@echo "  setup      - Initial setup (create .env, directories)"
	@echo "  start      - Start all services"
	@echo "  stop       - Stop all services"
	@echo "  restart    - Restart all services"
	@echo "  logs       - Show logs (use LOGS_SERVICE=name for specific service)"
	@echo "  status     - Show service status"
	@echo "  build      - Build/rebuild containers (if needed)"
	@echo "  clean      - Remove containers and volumes (DANGER!)"
	@echo ""
	@echo "Examples:"
	@echo "  make start"
	@echo "  make logs LOGS_SERVICE=grafana"
	@echo "  make restart"

# Setup: create .env if missing
setup:
	@echo "=== Setting up Monitoring v2 ==="
	@if [ ! -f .env ]; then \
		echo "Creating .env from template..."; \
		cp env.template .env; \
		echo "Please edit .env to configure your deployment"; \
	else \
		echo ".env already exists"; \
	fi
	@mkdir -p data/{prometheus,grafana,graphite}
	@mkdir -p config/{prometheus,grafana/{provisioning/{datasources,dashboards},dashboards}}
	@echo ""
	@echo "Setup complete! Next steps:"
	@echo "  1. Edit .env to configure your deployment"
	@echo "  2. Run 'make start' to start services"

# Start services
start:
	@echo "Starting Monitoring v2 services..."
	docker compose up -d
	@echo ""
	@echo "Services starting. Access:"
	@echo "  Grafana:     http://localhost:$${GRAFANA_PORT:-9032}"
	@echo "  Prometheus:  http://localhost:$${PROMETHEUS_PORT:-9033}"
	@echo "  Graphite:    http://localhost:8080"

# Stop services
stop:
	@echo "Stopping services..."
	docker compose down

# Restart services
restart: stop start

# Show logs
LOGS_SERVICE ?= 
logs:
ifdef LOGS_SERVICE
	docker compose logs -f $(LOGS_SERVICE)
else
	docker compose logs -f
endif

# Show status
status:
	@echo "=== Service Status ==="
	@docker compose ps
	@echo ""
	@echo "=== Health Checks ==="
	@echo "Prometheus:   $$(curl -s http://localhost:$${PROMETHEUS_PORT:-9033}/-/healthy 2>/dev/null || echo 'unreachable')"
	@echo "Grafana:      $$(curl -s http://localhost:$${GRAFANA_PORT:-9032}/api/health 2>/dev/null | head -c 50 || echo 'unreachable')"
	@echo "Graphite:     $$(nc -z localhost $${GRAPHITE_PORT:-9038} 2>/dev/null && echo 'OK' || echo 'unreachable')"

# Build containers (mostly for future custom images)
build:
	@echo "Building containers..."
	docker compose build

# Clean everything (DANGER!)
clean:
	@echo "WARNING: This will remove all containers and volumes!"
	@read -p "Are you sure? [y/N] " confirm && [ "$$confirm" = "y" ] || exit 1
	docker compose down -v
	@echo "Cleaned."

# Quick commands
ps:
	docker compose ps

up: start
down: stop
