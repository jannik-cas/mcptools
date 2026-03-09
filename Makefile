.PHONY: install test lint format clean

install:
	pip install -e ".[dev]"

test:
	pytest --cov=mcptools --cov-report=term-missing --cov-report=xml -v

lint:
	ruff check .
	ruff format --check .

format:
	ruff format .
	ruff check --fix .

clean:
	rm -rf build/ dist/ *.egg-info .pytest_cache .coverage coverage.xml htmlcov/
	find . -type d -name __pycache__ -exec rm -rf {} +
