.PHONY: install lint test run docker-build docker-up docker-down ingest clean help

PYTHON := python
PIP := pip
RUFF := ruff
PYTEST := pytest

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

install: ## Install dependencies
	$(PIP) install -e ".[dev]"

lint: ## Run linter
	$(RUFF) check src/ tests/
	$(RUFF) format --check src/ tests/

test: ## Run tests
	$(PYTEST) tests/ -v --tb=short

run: ## Run the API server
	uvicorn src.api.app:app --host 0.0.0.0 --port 8000 --reload

docker-build: ## Build Docker image
	docker build -t adops-agent-platform .

docker-up: ## Start services via docker-compose
	docker-compose up -d

docker-down: ## Stop services via docker-compose
	docker-compose down

ingest: ## Run data ingestion pipeline
	$(PYTHON) -m src.ingestion.pipeline

clean: ## Remove build artifacts
	rm -rf build/ dist/ *.egg-info .pytest_cache .ruff_cache .mypy_cache
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
