"""EPIC 3.4 / 4.5 Dart-in-Python lint script tests."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LINT = ROOT / "scripts" / "lint_dart_in_python.py"
COUNT_BASELINE = ROOT / "tests" / "fixtures" / "lint" / "dart_sniff_baseline.json"
FINGERPRINT_BASELINE = ROOT / "linters" / "emitter_baseline.txt"


def test_lint_script_passes_with_baseline() -> None:
    result = subprocess.run(
        [sys.executable, str(LINT)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr or result.stdout


def test_baseline_files_exist() -> None:
    assert COUNT_BASELINE.is_file()
    assert FINGERPRINT_BASELINE.is_file()
    payload = json.loads(COUNT_BASELINE.read_text(encoding="utf-8"))
    assert payload["layout_widgets_count"] > 0
    lines = [
        line
        for line in FINGERPRINT_BASELINE.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.startswith("#")
    ]
    assert len(lines) > 0


def test_fingerprint_swap_is_detected_as_new_debt() -> None:
    from scripts.lint_dart_in_python import (
        ViolationFingerprint,
        load_fingerprint_baseline,
    )

    baseline = load_fingerprint_baseline()
    assert baseline
    first = baseline[sorted(baseline)[0]]
    swapped_key = ViolationFingerprint(
        path=first.path,
        snippet_hash="00000000",
        category=first.category,
        owner_epic=first.owner_epic,
    ).key
    current_keys = (set(baseline) - {first.key}) | {swapped_key}
    new_fingerprints = current_keys - set(baseline)
    assert swapped_key in new_fingerprints


def test_blocking_ir_zone_has_zero_current_violations() -> None:
    from scripts.lint_dart_in_python import collect_blocking_violations

    assert collect_blocking_violations() == []
