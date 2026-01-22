# Makefile for MELCloud Home Integration

.PHONY: help install lint format format-check type-check test test-api test-integration test-e2e test-ha pre-commit clean dev-up dev-down dev-restart dev-reset dev-reset-full dev-logs dev-rebuild deploy deploy-test deploy-watch version-patch version-minor version-major release

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

format-check:  ## Check code formatting (CI mode)
	uv run ruff format --check custom_components/

type-check:  ## Run mypy type checker
	uv run mypy --ignore-missing-imports --explicit-package-bases custom_components/melcloudhome/

test-api:  ## API unit tests only (~208 tests)
	@rm -f .coverage coverage.xml
	uv run pytest tests/api/ -v -m "not e2e" \
		--cov=custom_components/melcloudhome \
		--cov-report=xml \
		--cov-report=html \
		--cov-report=term-missing

test-integration:  ## Integration tests only (~123 tests)
	@rm -f .coverage coverage.xml
	docker compose -f docker-compose.test.yml up -d melcloud-mock
	docker compose -f docker-compose.test.yml run --rm integration-tests \
		sh -c "uv pip install pytest-homeassistant-custom-component && \
		       uv run pytest tests/integration/ -v \
		         --cov=custom_components/melcloudhome \
		         --cov-report=xml \
		         --cov-report=html \
		         --cov-report=term-missing"
	docker compose -f docker-compose.test.yml down -v

test-e2e:  ## E2E tests only (~13 tests)
	@rm -f .coverage coverage.xml
	docker compose -f docker-compose.test.yml up -d melcloud-mock
	docker compose -f docker-compose.test.yml run --rm e2e-tests \
		sh -c "uv run pytest tests/api/ -m e2e -v \
		         --cov=custom_components/melcloudhome \
		         --cov-report=xml \
		         --cov-report=html \
		         --cov-report=term-missing"
	docker compose -f docker-compose.test.yml down -v

test:  ## Run ALL tests with combined coverage (~344 tests)
	@rm -f .coverage coverage.xml
	@rm -rf htmlcov coverage-output
	@mkdir -p coverage-output
	@echo "🧪 API unit tests..."
	@uv run pytest tests/api/ -v -m "not e2e" \
		--cov=custom_components/melcloudhome \
		--cov-report=
	@cp .coverage coverage-output/.coverage
	@echo "🐳 Integration + E2E..."
	@docker compose -f docker-compose.test.yml up \
		--abort-on-container-exit --exit-code-from e2e-tests; \
	EXIT_CODE=$$?; \
	docker compose -f docker-compose.test.yml down -v; \
	if [ -f coverage-output/.coverage ]; then cp coverage-output/.coverage .coverage; fi; \
	if [ -f coverage-output/coverage.xml ]; then cp coverage-output/coverage.xml coverage.xml; fi; \
	if [ -d coverage-output/htmlcov ]; then cp -r coverage-output/htmlcov htmlcov; fi; \
	echo "📊 Coverage: open htmlcov/index.html"; \
	exit $$EXIT_CODE

test-ha:  ## Deprecated - use 'make test' instead
	@echo "⚠️  Deprecated: 'make test-ha' is now 'make test'"
	@echo "    Integration + E2E tests run via Docker Compose"
	@echo "    Update your documentation and scripts"
	@$(MAKE) test

pre-commit:  ## Run all pre-commit hooks
	uv run pre-commit run --all-files

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

dev-reset:  ## Reset dev environment (restore to clean snapshot with dev user)
	docker compose -f docker-compose.dev.yml down
	rm -rf dev-config/.storage dev-config/home-assistant*.db* dev-config/home-assistant.log*
	cp -r dev-config-template/.storage dev-config/
	docker compose -f docker-compose.dev.yml up -d
	@echo "✅ Dev environment reset to clean snapshot"
	@echo "🌐 Home Assistant: http://localhost:8123 (dev/dev)"
	@echo "➕ Add integration via Settings → Devices & Services"

dev-reset-full:  ## Complete reset (wipe everything, run init script)
	docker compose -f docker-compose.dev.yml down
	rm -rf dev-config/.storage dev-config/*.db* dev-config/*.log* dev-config/*.yaml
	docker compose -f docker-compose.dev.yml up -d
	@echo "✅ Dev environment completely reset"
	@echo "🌐 Home Assistant: http://localhost:8123"
	@echo "⚠️  You'll need to create user and configure integration"

dev-snapshot:  ## Save current dev environment state (SNAPSHOT=path/to/save)
	@if [ -z "$(SNAPSHOT)" ]; then \
		echo "❌ Error: SNAPSHOT parameter required"; \
		echo "Usage: make dev-snapshot SNAPSHOT=dev-config-snapshots/my-test-state"; \
		exit 1; \
	fi
	@if [ ! "$$(docker ps -q -f name=ha-melcloud-dev)" ]; then \
		echo "❌ Error: Home Assistant container not running"; \
		echo "Start it first with: make dev-up"; \
		exit 1; \
	fi
	@mkdir -p $(SNAPSHOT)
	docker cp ha-melcloud-dev:/config/.storage $(SNAPSHOT)/
	docker cp ha-melcloud-dev:/config/.storage/core.entity_registry $(SNAPSHOT)/entity_registry.json
	docker cp ha-melcloud-dev:/config/.storage/core.device_registry $(SNAPSHOT)/device_registry.json
	@echo "✅ Snapshot saved to: $(SNAPSHOT)"
	@echo "📊 Restore with: make dev-restore-snapshot SNAPSHOT=$(SNAPSHOT)"

dev-restore-snapshot:  ## Restore dev environment from snapshot (SNAPSHOT=path/to/snapshot)
	@if [ -z "$(SNAPSHOT)" ]; then \
		echo "❌ Error: SNAPSHOT parameter required"; \
		echo "Usage: make dev-restore-snapshot SNAPSHOT=dev-config-snapshots/scenario-a-real-api/prod-baseline"; \
		exit 1; \
	fi
	@if [ ! -d "$(SNAPSHOT)/.storage" ]; then \
		echo "❌ Error: Snapshot not found: $(SNAPSHOT)/.storage"; \
		exit 1; \
	fi
	docker compose -f docker-compose.dev.yml down
	rm -rf dev-config/.storage
	cp -r $(SNAPSHOT)/.storage dev-config/
	docker compose -f docker-compose.dev.yml up homeassistant -d
	@echo "✅ Dev environment restored from snapshot: $(SNAPSHOT)"
	@echo "🌐 Home Assistant: http://localhost:8123"
	@echo "⚠️  Mock server NOT started (use 'make dev-up' if needed)"

dev-logs:  ## View Home Assistant logs (Ctrl+C to exit)
	docker compose -f docker-compose.dev.yml logs -f homeassistant

dev-rebuild:  ## Rebuild mock server image (after updating mock server code)
	docker compose -f docker-compose.dev.yml down
	docker compose -f docker-compose.dev.yml build --no-cache melcloud-mock
	docker compose -f docker-compose.dev.yml up -d
	@echo "✅ Mock server rebuilt and restarted"

# Production deployment commands (pre-release testing only)
deploy:  ## Deploy to production HA (requires .env with HA_SSH_HOST, HA_CONTAINER)
	uv run python tools/deploy_custom_component.py melcloudhome

deploy-test:  ## Deploy to production HA and test via API
	uv run python tools/deploy_custom_component.py melcloudhome --test

deploy-watch:  ## Deploy to production HA and watch logs
	uv run python tools/deploy_custom_component.py melcloudhome --watch

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
