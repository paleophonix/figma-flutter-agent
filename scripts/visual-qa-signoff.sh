#!/usr/bin/env bash
# Visual QA offline gate: golden/visual pytest subset + demo-signoff --visual-qa profile.
set -euo pipefail
cd "$(dirname "$0")/.."
poetry run pytest -q tests/test_golden_generation.py tests/test_visual_qa_profile.py tests/test_visual_qa_compare.py
poetry run figma-flutter demo-signoff --strict --signoff-gates --visual-qa
echo "Visual QA sign-off OK"
