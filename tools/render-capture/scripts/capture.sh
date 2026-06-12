#!/usr/bin/env bash
set -euo pipefail

FEATURE_NAME="${FEATURE_NAME:?FEATURE_NAME is required}"
GOLDEN_TEST="test/golden/${FEATURE_NAME}_screen_test.dart"
GOLDEN_PNG="test/goldens/${FEATURE_NAME}_screen.png"

cd /capture

flutter pub get

EXTRA_ARGS=()
if [[ "${UPDATE_GOLDENS:-0}" == "1" ]]; then
  EXTRA_ARGS+=(--update-goldens)
fi

flutter test "$GOLDEN_TEST" "${EXTRA_ARGS[@]}"

if [[ ! -f "$GOLDEN_PNG" ]]; then
  echo "golden PNG not written: $GOLDEN_PNG" >&2
  exit 1
fi
