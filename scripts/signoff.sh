#!/usr/bin/env bash
# Offline release gate (spec §23 fixtures + unit tests). Requires Poetry.
set -euo pipefail
cd "$(dirname "$0")/.."
poetry run ruff check .
poetry run ruff format --check .
poetry run mypy src tests
poetry run figma-flutter demo-signoff --strict --signoff-gates
if [ -x tools/build_sidecars.sh ]; then
  tools/build_sidecars.sh
fi
poetry run pytest -q -m "not live_figma"

if [ "${FIGMA_SIGNOFF_DOCKER:-}" = "1" ]; then
  compose="$(dirname "$0")/../docker/render-capture/docker-compose.yml"
  docker compose -f "$compose" build golden-capture
  docker compose -f "$compose" run --rm golden-capture flutter --version
fi

echo "Sign-off OK"
