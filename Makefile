.PHONY: install test lint format build clean docker help

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-15s\033[0m %s\n", $$1, $$2}'

install: ## Install package with dev dependencies
	pip install -e ".[dev]"

test: ## Run tests with coverage
	PYTHONPATH=. pytest tests/ -v --tb=short -W ignore::pytest.PytestConfigWarning --cov=farm_agent --cov-report=term-missing

test-quick: ## Run tests without coverage
	PYTHONPATH=. pytest tests/ -v --tb=short -W ignore::pytest.PytestConfigWarning -W ignore::pytest.PytestConfigWarning
	PYTHONPATH=. pytest tests/ -v --tb=short -W ignore::pytest.PytestConfigWarning

lint: ## Lint and format code
	ruff check farm_agent/ --fix
	ruff format farm_agent/ tests/

lint-check: ## Check lint without fixing
	ruff check farm_agent/
	ruff format --check farm_agent/ tests/

build: ## Build Python package
	python -m build

docker: ## Build Docker image
	docker build -t farm_agent:latest .

docker-run: ## Run with Docker (dry run)
	docker run --rm -v $(PWD)/config.yaml:/home/farm_agent/config.yaml:ro farm_agent:latest run --dry-run

clean: ## Clean build artifacts
	rm -rf dist/ build/ *.egg-info .pytest_cache htmlcov .coverage
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true

stats: ## Show project statistics
	@echo "📁 Python files:"
	@find farm_agent -name "*.py" | wc -l
	@echo "📝 Lines of code:"
	@find farm_agent -name "*.py" -exec cat {} + | wc -l
	@echo "🧪 Test files:"
	@find tests -name "*.py" 2>/dev/null | wc -l || echo "0"
