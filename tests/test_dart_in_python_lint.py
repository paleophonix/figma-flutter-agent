"""EPIC 3.4 Dart-in-Python lint script tests."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LINT = ROOT / "scripts" / "lint_dart_in_python.py"
BASELINE = ROOT / "tests" / "fixtures" / "lint" / "dart_sniff_baseline.json"


def test_lint_script_passes_with_baseline() -> None:
    result = subprocess.run(
        [sys.executable, str(LINT)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr or result.stdout


def test_baseline_file_exists() -> None:
    assert BASELINE.is_file()
    payload = json.loads(BASELINE.read_text(encoding="utf-8"))
    assert payload["layout_widgets_count"] > 0
