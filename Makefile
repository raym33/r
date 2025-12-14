.PHONY: help install dev test lint format type-check clean build publish docs

PYTHON := python3
PIP := $(PYTHON) -m pip

help:  ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-15s\033[0m %s\n", $$1, $$2}'

install:  ## Install the package
	$(PIP) install -e .

dev:  ## Install with development dependencies
	$(PIP) install -e ".[dev]"
	pre-commit install

test:  ## Run tests
	pytest tests/ -v

test-cov:  ## Run tests with coverage
	pytest tests/ -v --cov=r_cli --cov-report=term-missing --cov-report=html

lint:  ## Run linter
	ruff check .

lint-fix:  ## Run linter with auto-fix
	ruff check --fix .

format:  ## Format code
	ruff format .

format-check:  ## Check code formatting
	ruff format --check .

type-check:  ## Run type checker
	mypy r_cli --ignore-missing-imports

check: lint format-check type-check test  ## Run all checks

clean:  ## Clean build artifacts
	rm -rf build/
	rm -rf dist/
	rm -rf *.egg-info/
	rm -rf .pytest_cache/
	rm -rf .mypy_cache/
	rm -rf .ruff_cache/
	rm -rf htmlcov/
	rm -rf .coverage
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete

build: clean  ## Build the package
	$(PYTHON) -m build

publish: build  ## Publish to PyPI (requires authentication)
	$(PYTHON) -m twine upload dist/*

publish-test: build  ## Publish to TestPyPI
	$(PYTHON) -m twine upload --repository testpypi dist/*

run:  ## Run R CLI in interactive mode
	$(PYTHON) -m r_cli.main

demo:  ## Run animation demo
	$(PYTHON) -m r_cli.main demo
