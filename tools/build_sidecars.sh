#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SIDECAR="$ROOT/tools/dart_ast_sidecar"
BIN="$ROOT/tools/bin"
mkdir -p "$BIN"

resolve_dart() {
  if command -v dart >/dev/null 2>&1; then
    command -v dart
    return 0
  fi
  local sdk="${FIGMA_FLUTTER_SDK:-${FLUTTER_ROOT:-}}"
  if [[ -z "$sdk" && -f "$ROOT/.env" ]]; then
    sdk="$(grep -E '^[[:space:]]*FIGMA_FLUTTER_SDK[[:space:]]*=' "$ROOT/.env" | head -1 | cut -d= -f2- | tr -d " \r\"'")"
  fi
  if [[ -n "$sdk" && -x "$sdk/bin/dart" ]]; then
    echo "$sdk/bin/dart"
    return 0
  fi
  return 1
}

DART="$(resolve_dart || true)"
if [[ -z "$DART" ]]; then
  echo "dart not found; set FIGMA_FLUTTER_SDK in .env or add Flutter bin to PATH" >&2
  exit 1
fi

case "$(uname -s)" in
  Linux*) OUT_NAME="ast_compiler-linux" ;;
  Darwin*) OUT_NAME="ast_compiler-macos" ;;
  MINGW* | MSYS* | CYGWIN*)
    OUT_NAME="ast_compiler.exe"
    ;;
  *)
    echo "Unsupported OS for native build: $(uname -s)" >&2
    exit 1
    ;;
esac

OUT="$BIN/$OUT_NAME"
echo "Using dart: $DART"
cd "$SIDECAR"
"$DART" pub get
"$DART" compile exe bin/ast_compiler.dart -o "$OUT"
echo "Built $OUT"

# Git Bash on Windows: also emit .exe when building from MSYS
if [[ "$OUT_NAME" != "ast_compiler.exe" ]] && { [[ "$(uname -s)" == MINGW* ]] || [[ -n "${WINDIR:-}" ]]; }; then
  "$DART" compile exe bin/ast_compiler.dart -o "$BIN/ast_compiler.exe"
  echo "Built $BIN/ast_compiler.exe"
fi
