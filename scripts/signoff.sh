#!/usr/bin/env bash
# Offline release gate (spec §23 fixtures + unit tests). Requires Poetry.
set -euo pipefail
cd "$(dirname "$0")/.."
poetry run ruff check .
poetry run ruff format --check .
poetry run mypy src tests
poetry run figma-flutter demo-signoff --strict --signoff-gates
poetry run pytest -q -m "not live_figma"
echo "Sign-off OK"
