# Common developer commands. Run `make help` to list them.
.DEFAULT_GOAL := help

PY := python
PIP := pip
COMPOSE := docker compose
BACKEND := backend

.PHONY: help install dev lint type test test-unit test-integ \
        docker-build up down logs ps health \
        celery-ping clean

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) \
	  | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-18s\033[0m %s\n", $$1, $$2}'

# ---------------- Local (no Docker) ----------------
install: ## Install runtime deps into the active env
	cd $(BACKEND) && $(PIP) install .

dev: ## Install runtime + dev deps
	cd $(BACKEND) && $(PIP) install -e ".[dev]"

lint: ## Run ruff
	cd $(BACKEND) && ruff check app tests

lint-fix: ## Auto-fix lint issues
	cd $(BACKEND) && ruff check --fix app tests

type: ## Run mypy
	cd $(BACKEND) && mypy app

test: ## Run all tests
	cd $(BACKEND) && pytest

test-unit: ## Run unit tests only (no infra)
	cd $(BACKEND) && pytest -m unit

test-integ: ## Run integration tests (needs Docker services)
	cd $(BACKEND) && pytest -m integration

# ---------------- Docker topology ----------------
docker-build: ## Build backend images
	$(COMPOSE) build

up: ## Start the full local stack (postgres, redis, api, worker, beat)
	$(COMPOSE) up -d

down: ## Stop the stack (keep data)
	$(COMPOSE) down

logs: ## Tail logs from all services
	$(COMPOSE) logs -f

ps: ## Show running services
	$(COMPOSE) ps

health: ## Hit the API health endpoint
	curl -fsS http://localhost:8000/health && echo

celery-ping: ## Round-trip a Celery task to prove the worker topology
	$(COMPOSE) exec api celery -A app.worker.celery_app call app.tasks.ping

# ---------------- Cleanup ----------------
clean: ## Remove caches and build artifacts
	find . -type d -name __pycache__ -prune -exec rm -rf {} +
	find . -type d -name .pytest_cache -prune -exec rm -rf {} +
	find . -type d -name .ruff_cache -prune -exec rm -rf {} +
	find . -type d -name .mypy_cache -prune -exec rm -rf {} +
	rm -rf $(BACKEND)/build $(BACKEND)/dist $(BACKEND)/*.egg-info
