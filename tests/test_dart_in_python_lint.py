"""EPIC 3.4 / 4.5 Dart-in-Python lint script tests."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LINT = ROOT / "scripts" / "lint_dart_in_python.py"
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


def test_fingerprint_baseline_exists() -> None:
    assert FINGERPRINT_BASELINE.is_file()
    lines = [
        line
        for line in FINGERPRINT_BASELINE.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.startswith("#")
    ]
    assert len(lines) > 0


def test_fingerprint_swap_is_detected_as_new_debt() -> None:
    from scripts.lint_baseline import (
        ViolationFingerprint,
        compare_fingerprints,
        load_fingerprint_baseline,
    )

    baseline = load_fingerprint_baseline(FINGERPRINT_BASELINE)
    assert baseline
    first = baseline[sorted(baseline)[0]]
    swapped_key = ViolationFingerprint(
        path=first.path,
        snippet_hash="00000000",
        category=first.category,
        owner_epic=first.owner_epic,
    ).key
    current_keys = (set(baseline) - {first.key}) | {swapped_key}
    current = [
        ViolationFingerprint(
            path=key.split("|")[0],
            snippet_hash=key.split("|")[1],
            category=key.split("|")[2],
            owner_epic=baseline.get(key, first).owner_epic if key in baseline else first.owner_epic,
        )
        for key in current_keys
    ]
    comparison = compare_fingerprints(baseline, current)
    assert swapped_key in comparison.added


def test_relocated_fingerprint_fails() -> None:
    from scripts.lint_baseline import (
        ViolationFingerprint,
        compare_fingerprints,
        load_fingerprint_baseline,
    )

    baseline = load_fingerprint_baseline(FINGERPRINT_BASELINE)
    first = baseline[sorted(baseline)[0]]
    relocated = ViolationFingerprint(
        path="src/figma_flutter_agent/generator/layout/widgets/relocated.py",
        snippet_hash=first.snippet_hash,
        category=first.category,
        owner_epic=first.owner_epic,
    )
    current = [
        item
        for key, item in baseline.items()
        if key != first.key
    ] + [relocated]
    comparison = compare_fingerprints(baseline, current)
    assert comparison.relocated
    assert not comparison.ok


def test_removed_fingerprint_is_burndown_not_failure() -> None:
    from scripts.lint_baseline import compare_fingerprints, load_fingerprint_baseline

    baseline = load_fingerprint_baseline(FINGERPRINT_BASELINE)
    first_key = sorted(baseline)[0]
    current = [item for key, item in baseline.items() if key != first_key]
    comparison = compare_fingerprints(baseline, current)
    assert first_key in comparison.removed
    assert not comparison.added
    assert not comparison.relocated
    assert comparison.ok


def test_blocking_ir_zone_has_zero_current_violations() -> None:
    from scripts.lint_dart_in_python import collect_blocking_violations

    assert collect_blocking_violations() == []
