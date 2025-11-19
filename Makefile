# Makefile for MELCloud Home Integration

.PHONY: help install lint format type-check test test-cov pre-commit clean

help:  ## Show this help message
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

install:  ## Install development dependencies
	pip install pre-commit ruff mypy
	pre-commit install

lint:  ## Run ruff linter
	uv run ruff check custom_components/

format:  ## Format code with ruff
	uv run ruff format custom_components/
	uv run ruff check --fix custom_components/

type-check:  ## Run mypy type checker
	uv run mypy custom_components/melcloudhome/

test:  ## Run tests
	uv run pytest tests/ -v

test-cov:  ## Run tests with coverage report
	uv run pytest tests/ --cov=custom_components/melcloudhome/api --cov-report=term-missing

pre-commit:  ## Run all pre-commit hooks
	pre-commit run --all-files

clean:  ## Clean up cache files
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".mypy_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".ruff_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name "htmlcov" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	find . -type f -name ".coverage" -delete 2>/dev/null || true

all: format lint type-check test  ## Run format, lint, type-check, and tests
