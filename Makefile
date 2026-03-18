# ============================================================
# NPC Dialogue Engine — Development Commands
# ============================================================
# Usage:  make <target>
#
#   make install      Install production + dev dependencies
#   make dev          Start all services (Docker Compose)
#   make down         Stop all services
#   make test         Run test suite
#   make lint         Run linter checks
#   make format       Auto-format code
#   make migrate      Run database migrations
#   make ingest       Ingest worldbuilding documents into ChromaDB
#   make clean        Remove build artifacts and caches
# ============================================================

.DEFAULT_GOAL := help
SHELL := /bin/bash

# Python
PYTHON ?= python
PIP ?= pip

# Docker
COMPOSE ?= docker compose

# -------------------------------------------------------
# Setup
# -------------------------------------------------------

.PHONY: install
install: ## Install production and dev dependencies
	$(PIP) install --upgrade pip
	$(PIP) install -e ".[dev]"
	$(PIP) install pre-commit
	pre-commit install

# -------------------------------------------------------
# Development
# -------------------------------------------------------

.PHONY: dev
dev: ## Start all services via Docker Compose
	$(COMPOSE) up --build -d
	@echo ""
	@echo "  API:      http://localhost:8000/docs"
	@echo "  Frontend: http://localhost:5173"
	@echo "  Metrics:  http://localhost:8000/metrics"
	@echo "  Health:   http://localhost:8000/health/detailed"
	@echo ""

.PHONY: down
down: ## Stop all services
	$(COMPOSE) down

.PHONY: logs
logs: ## Tail application logs
	$(COMPOSE) logs -f app

.PHONY: run
run: ## Run FastAPI server locally (without Docker)
	$(PYTHON) -m uvicorn src.api.main:app --reload --host 0.0.0.0 --port 8000

.PHONY: demo
demo: ## Run interactive CLI chat demo
	$(PYTHON) scripts/demo.py

# -------------------------------------------------------
# Quality
# -------------------------------------------------------

.PHONY: test
test: ## Run test suite with pytest
	$(PYTHON) -m pytest tests/ -v --tb=short

.PHONY: test-cov
test-cov: ## Run tests with coverage report
	$(PYTHON) -m pytest tests/ -v --tb=short --cov=src --cov-report=term-missing

.PHONY: lint
lint: ## Run ruff linter
	$(PYTHON) -m ruff check src/ tests/

.PHONY: format
format: ## Auto-format code with ruff
	$(PYTHON) -m ruff format src/ tests/
	$(PYTHON) -m ruff check --fix src/ tests/

.PHONY: typecheck
typecheck: ## Run type checker (mypy)
	$(PYTHON) -m mypy src/ --ignore-missing-imports

# -------------------------------------------------------
# Database
# -------------------------------------------------------

.PHONY: migrate
migrate: ## Run Alembic migrations (upgrade to latest)
	$(PYTHON) -m alembic upgrade head

.PHONY: migrate-new
migrate-new: ## Create a new migration (usage: make migrate-new MSG="add xyz")
	$(PYTHON) -m alembic revision --autogenerate -m "$(MSG)"

.PHONY: migrate-history
migrate-history: ## Show migration history
	$(PYTHON) -m alembic history --verbose

# -------------------------------------------------------
# Data
# -------------------------------------------------------

.PHONY: ingest
ingest: ## Ingest worldbuilding documents into ChromaDB
	$(PYTHON) scripts/ingest.py

.PHONY: evaluate
evaluate: ## Run RAG evaluation pipeline
	$(PYTHON) scripts/evaluate.py

# -------------------------------------------------------
# Cleanup
# -------------------------------------------------------

.PHONY: clean
clean: ## Remove build artifacts and caches
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .pytest_cache -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .ruff_cache -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	rm -rf build/ dist/ *.egg-info/ .coverage htmlcov/

# -------------------------------------------------------
# Help
# -------------------------------------------------------

.PHONY: help
help: ## Show this help message
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-18s\033[0m %s\n", $$1, $$2}'
