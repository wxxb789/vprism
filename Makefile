# Makefile for vprism development

.PHONY: help install test lint format type-check clean build docs dev-setup

help: ## Show this help message
	@echo "Available commands:"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

install: ## Install dependencies
	uv sync --all-extras --dev

test: ## Run tests with coverage
	uv run pytest tests/ --cov=vprism --cov-report=html --cov-report=term-missing

test-fast: ## Run tests without coverage
	uv run pytest tests/ -x -v

lint: ## Run linting checks
	uv run ruff check .

format: ## Format code
	uv run ruff format .

format-check: ## Check code formatting
	uv run ruff format --check .

type-check: ## Run type checking
	uv run mypy vprism/

clean: ## Clean build artifacts
	rm -rf build/
	rm -rf dist/
	rm -rf *.egg-info/
	rm -rf .pytest_cache/
	rm -rf .mypy_cache/
	rm -rf .ruff_cache/
	rm -rf htmlcov/
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete

build: ## Build package
	uv build

dev-setup: ## Set up development environment
	uv sync --all-extras --dev
	uv run pre-commit install

check-all: lint format-check type-check test ## Run all checks

ci: check-all ## Run CI checks locally

docs: ## Generate documentation
	@echo "Documentation generation not yet implemented"

release: ## Create a release (requires VERSION argument)
	@if [ -z "$(VERSION)" ]; then echo "Usage: make release VERSION=x.y.z"; exit 1; fi
	@echo "Creating release $(VERSION)"
	@echo "This would update version, create git tag, and trigger release process"