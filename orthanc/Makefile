# ═══════════════════════════════════════════════════════════════════════════════
# ORTHANC PACS - Makefile
# ═══════════════════════════════════════════════════════════════════════════════
# Common operations for managing Orthanc
#
# Usage: make <target>
#
# Override storage paths during setup:
#   make setup DICOM_STORAGE=/mnt/nas/dicom POSTGRES_STORAGE=/data/postgres
#
# ═══════════════════════════════════════════════════════════════════════════════

.PHONY: help setup install quick-setup start stop restart logs status clean reset uninstall upgrade backup restore backup-list validate seed-modalities rebuild menu sync-db-password

# Overridable variables with defaults
DICOM_STORAGE ?= /opt/orthanc/orthanc-storage
POSTGRES_STORAGE ?= /opt/orthanc/postgres-data
ORTHANC_AET ?= ORTHANC_LPCH

# Load .env if it exists (values from .env take precedence)
-include .env

# Default target
help:
	@echo "🏥 ORTHANC MANAGEMENT"
	@echo ""
	@echo "GETTING STARTED (after 'make setup' at repo root)"
	@echo "  make setup                  Create directories from .env (safe, keeps data)"
	@echo "  make start                  Start services"
	@echo ""
	@echo "ADVANCED SETUP"
	@echo "  make setup-wizard           Interactive wizard (custom paths, fresh install)"
	@echo "  make menu                   Full interactive menu"
	@echo ""
	@echo "SERVICE MANAGEMENT"
	@echo "  make start                  Start all services"
	@echo "  make stop                   Stop all services"
	@echo "  make restart                Restart all services"
	@echo "  make logs                   View logs (Ctrl+C to exit)"
	@echo "  make status                 Show service status"
	@echo ""
	@echo "MAINTENANCE"
	@echo "  make upgrade                Pull latest images and restart"
	@echo "  make clean                  Remove containers (keeps data)"
	@echo "  make reset                  Reset config (keeps data, regenerates .env)"
	@echo "  make uninstall              Remove everything (DANGER: deletes all data!)"
	@echo "  make seed-modalities        Add default DICOM destinations"
	@echo "  make validate               Check configuration"
	@echo "  make sync-db-password       Sync .env password to running database"
	@echo ""
	@echo "BACKUP/RESTORE"
	@echo "  make backup                 Create backup of DICOM data and database"
	@echo "  make restore FILE=path      Restore from backup file"
	@echo "  make backup-list            List available backups"
	@echo ""
	@echo "PORTS (defaults - 9010 series)"
	@echo "  9010  Operator Dashboard"
	@echo "  9011  Orthanc Web UI / API"
	@echo "  9012  OHIF Viewer"
	@echo "  9013  PostgreSQL"
	@echo "  9014  Routing API"
	@echo "  4242  DICOM"
	@echo ""
	@echo "  Grafana dashboards are in monitoring stack (port 9032)"
	@echo ""
	@echo "EXAMPLES"
	@echo "  # First time setup with custom NAS storage:"
	@echo "  make setup DICOM_STORAGE=/mnt/nas/orthanc/dicom"
	@echo ""
	@echo "  # Re-run setup to change paths (keeps existing data):"
	@echo "  make setup"
	@echo ""
	@echo "  # Complete uninstall (removes all data!):"
	@echo "  make uninstall"

# ─────────────────────────────────────────────────────────────────────────────────
# INTERACTIVE MENU
# ─────────────────────────────────────────────────────────────────────────────────

# Full interactive menu (for advanced options: custom paths, fresh install, backup/restore)
menu:
	@chmod +x setup.sh
	@./setup.sh

# ─────────────────────────────────────────────────────────────────────────────────
# SETUP
# ─────────────────────────────────────────────────────────────────────────────────

# Simple setup: create directories from .env (NEVER deletes data)
# Use this after running 'make setup' at the repo root
setup:
	@echo "🏥 ORTHANC SETUP"
	@echo ""
	@if [ ! -f .env ]; then \
		echo "❌ .env not found!"; \
		echo "   Run 'make setup' from repo root first, or copy from template:"; \
		echo "   cp config/env.template .env"; \
		exit 1; \
	fi
	@echo "📋 Configuration:"
	@grep -E "^(DICOM_STORAGE|POSTGRES_STORAGE|ORTHANC_AET)=" .env | sed 's/^/   /'
	@echo ""
	@echo "📁 Creating directories (if needed)..."
	@. ./.env && mkdir -p "$$DICOM_STORAGE" 2>/dev/null && echo "   ✅ $$DICOM_STORAGE" || echo "   ⚠️  Need sudo for $$DICOM_STORAGE"
	@. ./.env && mkdir -p "$$POSTGRES_STORAGE" 2>/dev/null && echo "   ✅ $$POSTGRES_STORAGE" || echo "   ⚠️  Need sudo for $$POSTGRES_STORAGE"
	@echo ""
	@echo "🔐 Setting permissions..."
	@. ./.env && (chown -R 1000:1000 "$$DICOM_STORAGE" 2>/dev/null || sudo chown -R 1000:1000 "$$DICOM_STORAGE" 2>/dev/null || echo "   ⚠️  Could not set DICOM_STORAGE ownership")
	@. ./.env && (chown -R 999:999 "$$POSTGRES_STORAGE" 2>/dev/null || sudo chown -R 999:999 "$$POSTGRES_STORAGE" 2>/dev/null || echo "   ⚠️  Could not set POSTGRES_STORAGE ownership")
	@echo ""
	@echo "✅ Setup complete! Run 'make start' to start services."
	@echo ""
	@echo "💡 Your existing data (if any) is preserved."

# Interactive setup wizard (for custom paths, fresh install, etc.)
setup-wizard:
	@chmod +x setup.sh
	@DICOM_STORAGE="$(DICOM_STORAGE)" \
	 POSTGRES_STORAGE="$(POSTGRES_STORAGE)" \
	 ORTHANC_AET="$(ORTHANC_AET)" \
	 ./setup.sh --setup

# Quick setup with defaults or overrides
quick-setup:
	@chmod +x setup.sh
	@./setup.sh --defaults \
		--dicom "$(DICOM_STORAGE)" \
		--db "$(POSTGRES_STORAGE)" \
		--aet "$(ORTHANC_AET)"

# Alias for backwards compatibility
install: setup-wizard

# ─────────────────────────────────────────────────────────────────────────────────
# SERVICE MANAGEMENT
# ─────────────────────────────────────────────────────────────────────────────────

start:
	@docker compose up -d
	@echo "⏳ Waiting for database to be ready..."
	@sleep 3
	@$(MAKE) -s sync-db-password || true
	@echo "✅ Services started"
	@echo ""
	@echo "  Dashboard: http://localhost:$${OPERATOR_UI_PORT:-9010}"
	@echo "  Orthanc:   http://localhost:$${ORTHANC_WEB_PORT:-9011}"
	@echo "  OHIF:      http://localhost:$${OHIF_PORT:-9012}"

# Sync database password from .env to running PostgreSQL
# This fixes the issue where POSTGRES_PASSWORD only works on first init
sync-db-password:
	@if [ -f .env ]; then \
		. ./.env && \
		echo "🔐 Syncing database password..." && \
		docker exec orthanc-postgres psql -U postgres -c "ALTER USER $${POSTGRES_USER:-orthanc} WITH PASSWORD '$${POSTGRES_PASSWORD}';" > /dev/null 2>&1 && \
		echo "   ✅ Password synced" || \
		echo "   ⚠️  Could not sync password (database may still be starting)"; \
	fi

stop:
	@docker compose stop
	@echo "✅ Services stopped"

restart:
	@docker compose restart
	@echo "✅ Services restarted"

# Rebuild and restart (use after code changes to api/)
rebuild:
	@echo "🔨 Rebuilding containers..."
	@docker compose build
	@docker compose up -d
	@echo "✅ Rebuilt and restarted"

logs:
	@docker compose logs -f

status:
	@./orthanc status

# ─────────────────────────────────────────────────────────────────────────────────
# MAINTENANCE
# ─────────────────────────────────────────────────────────────────────────────────

upgrade:
	@echo "📥 Pulling latest images..."
	@docker compose pull
	@echo "🔄 Restarting services..."
	@docker compose up -d
	@echo "✅ Upgrade complete"

# Create backup of DICOM data and PostgreSQL database
backup:
	@chmod +x setup.sh
	@./setup.sh --backup

# Restore from backup file (requires FILE=path)
restore:
ifndef FILE
	@echo "❌ Usage: make restore FILE=backups/orthanc-backup-YYYYMMDD-HHMMSS.tar.gz"
	@echo ""
	@echo "Available backups:"
	@ls -la backups/*.tar.gz 2>/dev/null || echo "  No backups found in ./backups/"
else
	@chmod +x setup.sh
	@./setup.sh --restore $(FILE)
endif

# List available backups
backup-list:
	@echo "📦 Available backups:"
	@ls -lah backups/*.tar.gz 2>/dev/null || echo "  No backups found in ./backups/"

clean:
	@docker compose down
	@echo "✅ Containers removed (data preserved)"
	@echo ""
	@echo "Data locations:"
	@echo "  DICOM:    $(DICOM_STORAGE)"
	@echo "  Postgres: $(POSTGRES_STORAGE)"

reset:
	@echo "🔄 Resetting configuration..."
	@docker compose down 2>/dev/null || true
	@rm -f .env
	@echo "✅ Configuration reset. Data preserved."
	@echo ""
	@echo "Run 'make setup' to reconfigure."

uninstall:
	@echo ""
	@echo "⚠️  WARNING: This will permanently delete:"
	@echo "    - All Docker containers and volumes"
	@echo "    - Configuration file (.env)"
	@echo "    - DICOM storage: $(DICOM_STORAGE)"
	@echo "    - PostgreSQL data: $(POSTGRES_STORAGE)"
	@echo ""
	@read -p "Are you sure? Type 'yes' to confirm: " confirm && \
	if [ "$$confirm" = "yes" ]; then \
		echo ""; \
		echo "🗑️  Stopping and removing containers..."; \
		docker compose down -v --remove-orphans 2>/dev/null || true; \
		echo "🗑️  Removing configuration..."; \
		rm -f .env; \
		echo "🗑️  Removing DICOM storage..."; \
		sudo rm -rf "$(DICOM_STORAGE)" 2>/dev/null || rm -rf "$(DICOM_STORAGE)" 2>/dev/null || echo "    (could not remove, may need manual deletion)"; \
		echo "🗑️  Removing PostgreSQL data..."; \
		sudo rm -rf "$(POSTGRES_STORAGE)" 2>/dev/null || rm -rf "$(POSTGRES_STORAGE)" 2>/dev/null || echo "    (could not remove, may need manual deletion)"; \
		echo ""; \
		echo "✅ Uninstall complete."; \
	else \
		echo "Cancelled."; \
	fi

# ─────────────────────────────────────────────────────────────────────────────────
# DEVELOPMENT
# ─────────────────────────────────────────────────────────────────────────────────

dev-shell:
	@docker compose exec orthanc /bin/bash

dev-db:
	@docker compose exec orthanc-db psql -U orthanc -d orthanc

dev-logs-orthanc:
	@docker compose logs -f orthanc

dev-logs-db:
	@docker compose logs -f orthanc-db

# ─────────────────────────────────────────────────────────────────────────────────
# VALIDATION
# ─────────────────────────────────────────────────────────────────────────────────

validate:
	@echo "🔍 Validating configuration..."
	@[ -f .env ] && echo "  ✅ .env file exists" || echo "  ❌ .env file missing (run: make setup)"
	@[ -f config/orthanc.json ] && echo "  ✅ orthanc.json exists" || echo "  ❌ orthanc.json missing"
	@[ -d "$(DICOM_STORAGE)" ] && echo "  ✅ DICOM storage exists: $(DICOM_STORAGE)" || echo "  ⚠️  DICOM storage missing: $(DICOM_STORAGE)"
	@[ -d "$(POSTGRES_STORAGE)" ] && echo "  ✅ Postgres storage exists: $(POSTGRES_STORAGE)" || echo "  ⚠️  Postgres storage missing: $(POSTGRES_STORAGE)"
	@docker compose config > /dev/null && echo "  ✅ docker-compose.yml valid" || echo "  ❌ docker-compose.yml invalid"
	@echo ""
	@echo "Run 'make setup' to fix any issues."

# Manually seed default DICOM modalities
# Run with: sudo make seed-modalities
seed-modalities:
	@echo "🌱 Seeding default DICOM modalities..."
	@USER=$$(cat .env | grep "^ORTHANC_USERNAME=" | cut -d= -f2) && \
	 PASS=$$(cat .env | grep "^ORTHANC_PASSWORD=" | cut -d= -f2) && \
	 PORT=$$(cat .env | grep "^ORTHANC_WEB_PORT=" | cut -d= -f2) && \
	 PORT=$${PORT:-9011} && \
	 echo "  Using port $$PORT, user $$USER" && \
	 curl -sf -u "$$USER:$$PASS" -X PUT "http://localhost:$$PORT/modalities/MERCURE" \
		-H "Content-Type: application/json" -d '{"AET":"MERCURE","Host":"172.17.0.1","Port":11112}' && echo "  ✅ MERCURE" || echo "  ❌ MERCURE"
	@USER=$$(cat .env | grep "^ORTHANC_USERNAME=" | cut -d= -f2) && \
	 PASS=$$(cat .env | grep "^ORTHANC_PASSWORD=" | cut -d= -f2) && \
	 PORT=$$(cat .env | grep "^ORTHANC_WEB_PORT=" | cut -d= -f2) && \
	 PORT=$${PORT:-9011} && \
	 curl -sf -u "$$USER:$$PASS" -X PUT "http://localhost:$$PORT/modalities/LPCHROUTER" \
		-H "Content-Type: application/json" -d '{"AET":"LPCHROUTER","Host":"10.50.133.21","Port":4000}' && echo "  ✅ LPCHROUTER" || echo "  ❌ LPCHROUTER"
	@USER=$$(cat .env | grep "^ORTHANC_USERNAME=" | cut -d= -f2) && \
	 PASS=$$(cat .env | grep "^ORTHANC_PASSWORD=" | cut -d= -f2) && \
	 PORT=$$(cat .env | grep "^ORTHANC_WEB_PORT=" | cut -d= -f2) && \
	 PORT=$${PORT:-9011} && \
	 curl -sf -u "$$USER:$$PASS" -X PUT "http://localhost:$$PORT/modalities/LPCHTROUTER" \
		-H "Content-Type: application/json" -d '{"AET":"LPCHTROUTER","Host":"10.50.130.114","Port":4000}' && echo "  ✅ LPCHTROUTER" || echo "  ❌ LPCHTROUTER"
	@USER=$$(cat .env | grep "^ORTHANC_USERNAME=" | cut -d= -f2) && \
	 PASS=$$(cat .env | grep "^ORTHANC_PASSWORD=" | cut -d= -f2) && \
	 PORT=$$(cat .env | grep "^ORTHANC_WEB_PORT=" | cut -d= -f2) && \
	 PORT=$${PORT:-9011} && \
	 curl -sf -u "$$USER:$$PASS" -X PUT "http://localhost:$$PORT/modalities/MODLINK" \
		-H "Content-Type: application/json" -d '{"AET":"PSRTBONEAPP01","Host":"10.251.201.59","Port":104}' && echo "  ✅ MODLINK" || echo "  ❌ MODLINK"
	@echo ""
	@echo "Done! Verify with: curl -s -u user:pass http://localhost:9011/modalities | jq"
