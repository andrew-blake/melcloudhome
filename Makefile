# Makefile for MELCloud Home Integration

.PHONY: help install lint format type-check test pre-commit clean

help:  ## Show this help message
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

install:  ## Install development dependencies
	pip install pre-commit ruff mypy
	pre-commit install

lint:  ## Run ruff linter
	ruff check custom_components/

format:  ## Format code with ruff
	ruff format custom_components/
	ruff check --fix custom_components/

type-check:  ## Run mypy type checker
	mypy custom_components/melcloudhome/

pre-commit:  ## Run all pre-commit hooks
	pre-commit run --all-files

test:  ## Run tests (when implemented)
	@echo "Tests not yet implemented"

clean:  ## Clean up cache files
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".mypy_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".ruff_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true

all: format lint type-check  ## Run format, lint, and type-check
