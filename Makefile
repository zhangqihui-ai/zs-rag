SHELL := /bin/bash

COMPOSE := docker compose
BACKEND_DIR := backend
WEB_DIR := web

# ======================================
# Docker Compose Services
# ======================================

.PHONY: up down logs restart
.PHONY: up-prod down-prod logs-prod
.PHONY: build build-prod
.PHONY: migrate backend-install backend-dev web-install web-dev
.PHONY: dev-all help

# Start all services in development mode
up:
	$(COMPOSE) up -d
	@echo "✓ Development services started"
	@echo "  Frontend: http://localhost:80"
	@echo "  Backend:  http://localhost:8000"
	@echo "  API Docs: http://localhost:8000/docs"

# Start all services in production mode
up-prod:
	$(COMPOSE) -f docker-compose.prod.yml up -d --build
	@echo "✓ Production services started"

# Stop all services
down:
	$(COMPOSE) down

# Stop production services
down-prod:
	$(COMPOSE) -f docker-compose.prod.yml down

# View logs
logs:
	$(COMPOSE) logs -f $(service)

# View production logs
logs-prod:
	$(COMPOSE) -f docker-compose.prod.yml logs -f $(service)

# Restart services
restart:
	$(COMPOSE) restart

# ======================================
# Build Commands
# ======================================

# Build all services (development)
build:
	$(COMPOSE) build

# Build all services (production)
build-prod:
	$(COMPOSE) -f docker-compose.prod.yml build

# ======================================
# Database Migrations
# ======================================

# Run database migrations
migrate:
	@echo "Running database migrations..."
	$(COMPOSE) exec backend python -m alembic upgrade head
	@echo "✓ Migrations completed"

# Create new migration
migration:
	$(COMPOSE) exec backend python -m alembic revision --autogenerate -m "$(name)"

# ======================================
# Local Development (without Docker)
# ======================================

# Install backend dependencies
backend-install:
	python3 -m pip install -r $(BACKEND_DIR)/requirements.txt

# Run backend locally
backend-dev:
	cd $(BACKEND_DIR) && uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Install frontend dependencies
web-install:
	cd $(WEB_DIR) && npm install

# Run frontend locally
web-dev:
	cd $(WEB_DIR) && npm run dev -- --host 0.0.0.0 --port 5173

# Start all local development services
dev-all:
	@echo "Starting all local development services..."
	@$(COMPOSE) up -d postgres milvus neo4j
	@echo "Starting backend..."
	@cd $(BACKEND_DIR) && uvicorn app.main:app --reload --host 0.0.0.0 --port 8000 &
	@echo "Starting frontend..."
	@cd $(WEB_DIR) && npm run dev -- --host 0.0.0.0 --port 5173 &
	@echo "✓ All services started!"
	@echo "  Frontend: http://localhost:5173"
	@echo "  Backend:  http://localhost:8000"

# ======================================
# Utility Commands
# ======================================

# Clean up
clean:
	@echo "Cleaning up..."
	$(COMPOSE) down -v
	@echo "✓ Cleaned up all containers and volumes"

# Clean production
clean-prod:
	$(COMPOSE) -f docker-compose.prod.yml down -v

# Show help
help:
	@echo "ZS-RAG Development Commands"
	@echo "============================"
	@echo ""
	@echo "Docker Compose:"
	@echo "  make up           - Start development services"
	@echo "  make up-prod      - Start production services"
	@echo "  make down         - Stop development services"
	@echo "  make down-prod    - Stop production services"
	@echo "  make logs         - View logs (use: service=backend)"
	@echo "  make logs-prod    - View production logs"
	@echo "  make build        - Build development images"
	@echo "  make build-prod   - Build production images"
	@echo ""
	@echo "Database:"
	@echo "  make migrate      - Run database migrations"
	@echo "  make migration    - Create new migration (use: name=\"description\")"
	@echo ""
	@echo "Local Development:"
	@echo "  make backend-dev  - Run backend locally"
	@echo "  make web-dev      - Run frontend locally"
	@echo "  make dev-all      - Start all local services"
	@echo ""
	@echo "Utility:"
	@echo "  make clean        - Remove all containers and volumes"
	@echo "  make help         - Show this help"
