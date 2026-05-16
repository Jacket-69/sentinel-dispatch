.PHONY: help install dev test test-fast test-dataset lint format typecheck ci build-graph clean

PYTHON := uv run python
PYTEST := uv run pytest
RUFF := uv run ruff
MYPY := uv run mypy
UVICORN := uv run uvicorn

help: ## Mostrar esta ayuda
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

install: ## Instalar dependencias con uv (incluye dev)
	uv sync --all-groups

dev: ## Levantar servidor uvicorn con autoreload
	$(UVICORN) sentinel_dispatch.interfaces.api.main:app --reload --host 0.0.0.0 --port 8000

test: ## Correr todos los tests
	$(PYTEST)

test-fast: ## Solo unit tests (sin integration ni dataset)
	$(PYTEST) tests/unit -m "not slow"

test-dataset: ## Ejecutar dataset de aceptación (12 incidentes del SRS)
	$(PYTEST) -m dataset -v

lint: ## Lint + format check con ruff
	$(RUFF) check src tests scripts
	$(RUFF) format --check src tests scripts

format: ## Aplicar format con ruff
	$(RUFF) format src tests scripts
	$(RUFF) check --fix src tests scripts

typecheck: ## Typecheck con mypy
	$(MYPY) src

ci: lint typecheck test ## Pipeline completo (lo que corre en GitHub Actions)

build-graph: ## Pre-computar grafo OSM IV Región (~2 min, ~30-60 MB)
	$(PYTHON) scripts/build_graph.py

clean: ## Borrar caches y artifacts
	rm -rf .pytest_cache .mypy_cache .ruff_cache htmlcov .coverage coverage.xml
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
