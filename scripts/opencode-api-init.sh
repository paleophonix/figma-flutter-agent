#!/usr/bin/env bash
# Initialize OpenCode submodule with sparse checkout (API-only tree).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SPARSE="$ROOT/scripts/opencode-api-sparse.txt"
SUBMODULE="$ROOT/src/opencode"

if [[ ! -f "$SPARSE" ]]; then
  echo "Missing sparse path list: $SPARSE" >&2
  exit 1
fi

git -C "$ROOT" submodule update --init --depth 1 src/opencode

# Submodule may live on a filesystem without ownership metadata (common on Windows mounts).
git -C "$SUBMODULE" -c "safe.directory=$SUBMODULE" sparse-checkout init --no-cone
git -C "$SUBMODULE" -c "safe.directory=$SUBMODULE" sparse-checkout set --stdin <"$SPARSE"
git -C "$SUBMODULE" -c "safe.directory=$SUBMODULE" read-tree -mu HEAD

echo "OpenCode API sparse checkout ready under $SUBMODULE"
echo "Next: cd src/opencode && bun install && bun dev serve"
