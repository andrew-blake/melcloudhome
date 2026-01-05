# Makefile for MELCloud Home Integration

.PHONY: help install lint format type-check test test-ha test-cov pre-commit clean dev-up dev-down dev-restart dev-reset dev-logs dev-rebuild version-patch version-minor version-major release

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
	uv run mypy --ignore-missing-imports --explicit-package-bases custom_components/melcloudhome/

test:  ## Run API tests (no HA dependency)
	uv run pytest tests/api/ -v

test-ha:  ## Run HA integration tests in Docker (fast with caching)
	@docker build -q -t melcloudhome-test:latest -f tests/integration/Dockerfile . 2>/dev/null || true
	docker run --rm -v $(PWD):/app melcloudhome-test:latest

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

# Development environment commands (docker-compose)
dev-up:  ## Start dev environment (mock API + Home Assistant)
	docker compose -f docker-compose.dev.yml up -d
	@echo "✅ Dev environment started"
	@echo "🌐 Home Assistant: http://localhost:8123 (dev/dev)"
	@echo "🔧 Mock API: http://localhost:8080"

dev-down:  ## Stop dev environment
	docker compose -f docker-compose.dev.yml down

dev-restart:  ## Restart Home Assistant (quick reload after code changes)
	docker compose -f docker-compose.dev.yml restart homeassistant
	@echo "✅ Home Assistant restarted - code changes loaded"

dev-reset:  ## Reset dev environment (clear entity registry, fresh start)
	docker compose -f docker-compose.dev.yml down
	rm -rf dev-config/.storage
	docker compose -f docker-compose.dev.yml up -d
	@echo "✅ Dev environment reset - fresh entity registry"
	@echo "🌐 Home Assistant: http://localhost:8123 (dev/dev)"

dev-logs:  ## View Home Assistant logs (Ctrl+C to exit)
	docker compose -f docker-compose.dev.yml logs -f homeassistant

dev-rebuild:  ## Rebuild mock server image (after updating mock server code)
	docker compose -f docker-compose.dev.yml down
	docker compose -f docker-compose.dev.yml build --no-cache melcloud-mock
	docker compose -f docker-compose.dev.yml up -d
	@echo "✅ Mock server rebuilt and restarted"

# Version management commands
version-patch:  ## Bump patch version (x.y.Z)
	@CURRENT=$$(jq -r '.version' custom_components/melcloudhome/manifest.json); \
	NEW=$$(echo $$CURRENT | awk -F. '{$$3+=1; print $$1"."$$2"."$$3}'); \
	echo "Bumping version $$CURRENT -> $$NEW"; \
	jq --arg version "$$NEW" '.version = $$version' custom_components/melcloudhome/manifest.json > manifest.tmp && \
	mv manifest.tmp custom_components/melcloudhome/manifest.json; \
	{ head -7 CHANGELOG.md; echo ""; echo "## [$$NEW] - $$(date +%Y-%m-%d)"; echo ""; echo "### Added"; echo ""; echo "- "; echo ""; echo "### Changed"; echo ""; echo "- "; echo ""; echo "### Fixed"; echo ""; echo "- "; echo ""; echo "### Security"; echo ""; echo "- "; echo ""; tail -n +8 CHANGELOG.md; } > CHANGELOG.tmp && \
	mv CHANGELOG.tmp CHANGELOG.md; \
	echo "✅ Version bumped to $$NEW"; \
	echo "📝 Edit CHANGELOG.md to add release notes (delete unused sections)"; \
	echo "💾 Then run: git add . && git commit -m 'chore: Bump version to $$NEW'";

version-minor:  ## Bump minor version (x.Y.0)
	@CURRENT=$$(jq -r '.version' custom_components/melcloudhome/manifest.json); \
	NEW=$$(echo $$CURRENT | awk -F. '{$$2+=1; $$3=0; print $$1"."$$2"."$$3}'); \
	echo "Bumping version $$CURRENT -> $$NEW"; \
	jq --arg version "$$NEW" '.version = $$version' custom_components/melcloudhome/manifest.json > manifest.tmp && \
	mv manifest.tmp custom_components/melcloudhome/manifest.json; \
	{ head -7 CHANGELOG.md; echo ""; echo "## [$$NEW] - $$(date +%Y-%m-%d)"; echo ""; echo "### Added"; echo ""; echo "- "; echo ""; echo "### Changed"; echo ""; echo "- "; echo ""; echo "### Fixed"; echo ""; echo "- "; echo ""; echo "### Security"; echo ""; echo "- "; echo ""; tail -n +8 CHANGELOG.md; } > CHANGELOG.tmp && \
	mv CHANGELOG.tmp CHANGELOG.md; \
	echo "✅ Version bumped to $$NEW"; \
	echo "📝 Edit CHANGELOG.md to add release notes (delete unused sections)"; \
	echo "💾 Then run: git add . && git commit -m 'chore: Bump version to $$NEW'";

version-major:  ## Bump major version (X.0.0)
	@CURRENT=$$(jq -r '.version' custom_components/melcloudhome/manifest.json); \
	NEW=$$(echo $$CURRENT | awk -F. '{$$1+=1; $$2=0; $$3=0; print $$1"."$$2"."$$3}'); \
	echo "Bumping version $$CURRENT -> $$NEW"; \
	jq --arg version "$$NEW" '.version = $$version' custom_components/melcloudhome/manifest.json > manifest.tmp && \
	mv manifest.tmp custom_components/melcloudhome/manifest.json; \
	{ head -7 CHANGELOG.md; echo ""; echo "## [$$NEW] - $$(date +%Y-%m-%d)"; echo ""; echo "### Added"; echo ""; echo "- "; echo ""; echo "### Changed"; echo ""; echo "- "; echo ""; echo "### Fixed"; echo ""; echo "- "; echo ""; echo "### Security"; echo ""; echo "- "; echo ""; tail -n +8 CHANGELOG.md; } > CHANGELOG.tmp && \
	mv CHANGELOG.tmp CHANGELOG.md; \
	echo "✅ Version bumped to $$NEW"; \
	echo "📝 Edit CHANGELOG.md to add release notes (delete unused sections)"; \
	echo "💾 Then run: git add . && git commit -m 'chore: Bump version to $$NEW'";

release:  ## Create and push release tag (run after committing version bump)
	@VERSION=$$(jq -r '.version' custom_components/melcloudhome/manifest.json); \
	echo "Creating release tag v$$VERSION"; \
	if git tag | grep -q "^v$$VERSION$$"; then \
		echo "❌ Tag v$$VERSION already exists"; \
		exit 1; \
	fi; \
	if ! grep -q "\[$$VERSION\]" CHANGELOG.md; then \
		echo "❌ No CHANGELOG entry found for version $$VERSION"; \
		exit 1; \
	fi; \
	git tag -a "v$$VERSION" -m "Release v$$VERSION"; \
	echo "✅ Tag v$$VERSION created"; \
	echo "🚀 Push with: git push && git push --tags"; \
	echo "   This will trigger the release workflow"
