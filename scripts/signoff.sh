#!/usr/bin/env bash
# Offline release gate (spec §23 fixtures + unit tests). Requires Poetry.
set -euo pipefail
cd "$(dirname "$0")/.."
poetry run ruff check .
poetry run ruff format --check .
poetry run python scripts/lint_dart_in_python.py
poetry run mypy src tests
poetry run figma-flutter demo-signoff --strict --signoff-gates
poetry run figma-flutter fixture-ir-validate
if [ "${FIGMA_GEOMETRY_SIGNOFF:-1}" != "0" ]; then
  if [ -n "${FIGMA_GEOMETRY_SIGNOFF_SCREENS:-}" ]; then
    IFS=',' read -ra _geo_screens <<< "${FIGMA_GEOMETRY_SIGNOFF_SCREENS}"
    for _screen in "${_geo_screens[@]}"; do
      _screen="${_screen#"${_screen%%[![:space:]]*}"}"
      _screen="${_screen%"${_screen##*[![:space:]]}"}"
      [ -z "$_screen" ] && continue
      poetry run figma-flutter fixture-geometry-check --screen "$_screen"
    done
  else
    poetry run figma-flutter fixture-geometry-check
  fi
fi
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
