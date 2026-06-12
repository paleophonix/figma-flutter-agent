#!/usr/bin/env bash
# Offline release gate (spec §23 fixtures + unit tests). Requires Poetry.
set -euo pipefail
cd "$(dirname "$0")/.."
poetry run ruff check .
poetry run ruff format --check .
mkdir -p logs/lint
poetry run python scripts/lint_dart_in_python.py --write-burndown logs/lint/dart_debt_burndown.json
poetry run mypy src tests
poetry run figma-flutter demo-signoff --strict --signoff-gates
poetry run figma-flutter fixture-ir-validate
poetry run figma-flutter fidelity validate
if [ "${FIGMA_CORPUS_ORACLE_SIGNOFF:-1}" != "0" ]; then
  mkdir -p logs/oracle
  poetry run figma-flutter corpus-oracle gate --blocking --write-report-dir logs/oracle
fi
mkdir -p logs/semantics
poetry run figma-flutter semantics corpus-gate --write-report logs/semantics/w1_classification_gate.json
poetry run python scripts/semantics_legacy_burndown.py --write-report logs/semantics/legacy_burndown.json
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
