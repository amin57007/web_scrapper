.PHONY: help env install install-dev test test-all lint

PYTHON ?= python3
PIP ?= pip

help:
	@echo "web_scrapper / ulscrape targets:"
	@echo "  make env          - verify Python and imports (scripts/check_env.py)"
	@echo "  make install      - pip install runtime deps + editable package"
	@echo "  make install-dev  - same, plus pytest/ruff/mypy"
	@echo "  make test         - unit tests (no live Ultra Librarian network)"
	@echo "  make test-all     - full suite including live details-page scrape"
	@echo "  make lint         - ruff + mypy --strict on src/"

env:
	$(PYTHON) scripts/check_env.py

install:
	$(PIP) install -r requirements.txt
	$(PIP) install -e .

install-dev:
	$(PIP) install -r requirements-dev.txt
	$(PIP) install -e .

test:
	$(PYTHON) -m pytest -m "not network" -q

test-all:
	$(PYTHON) -m pytest -q

lint:
	ruff check src tests scripts
	mypy --strict src
