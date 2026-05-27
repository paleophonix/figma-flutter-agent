#!/usr/bin/env bash
# Manual E2E helper. Usage:
#   ./scripts/e2e-manual.sh "https://www.figma.com/design/FILE/Name?node-id=1-2" ../demo_app
set -euo pipefail

if [[ $# -lt 2 ]]; then
  echo "Usage: $0 <FIGMA_URL> <PROJECT_DIR>" >&2
  exit 1
fi

FIGMA_URL="$1"
PROJECT_DIR="$2"
cd "$(dirname "$0")/.."

echo "=== Offline sign-off ==="
bash scripts/signoff.sh

echo ""
echo "=== Live check ==="
poetry run figma-flutter live-check --figma-url "$FIGMA_URL" --dump --project-dir "$PROJECT_DIR"

echo ""
echo "=== Production generate ==="
poetry run figma-flutter generate --figma-url "$FIGMA_URL" --project-dir "$PROJECT_DIR"

echo ""
echo "=== Flutter analyze (in project) ==="
(
  cd "$PROJECT_DIR"
  dart format .
  flutter analyze
)

echo ""
echo "E2E helper finished. Complete runtime smoke manually: cd $PROJECT_DIR && flutter run -d chrome"
echo "Record results in tests/README.md (Manual E2E acceptance section)"
