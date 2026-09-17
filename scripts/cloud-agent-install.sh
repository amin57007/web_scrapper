#!/usr/bin/env bash
set -euo pipefail

# Idempotent Cloud Agent bootstrap for ulscrape.
python3 -m pip install -r requirements-dev.txt
python3 -m pip install -e .
python3 -m playwright install chromium
python3 scripts/check_env.py
