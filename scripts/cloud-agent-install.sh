#!/usr/bin/env bash
set -euo pipefail

# Idempotent Cloud Agent bootstrap for ulscrape.
# Works on main (script only) and on the scraper branch (full package).
if [ -f requirements-dev.txt ]; then
  python3 -m pip install -r requirements-dev.txt
else
  python3 -m pip install \
    'beautifulsoup4>=4.12' \
    'httpx>=0.27' \
    'pydantic>=2' \
    'typer>=0.12' \
    'rich>=13' \
    'playwright>=1.47' \
    'lxml>=5' \
    'pytest>=8' \
    'ruff>=0.6' \
    'mypy>=1.11'
fi
if [ -f pyproject.toml ]; then
  python3 -m pip install -e .
fi
python3 -m playwright install chromium
if [ -f scripts/check_env.py ]; then
  python3 scripts/check_env.py
fi
