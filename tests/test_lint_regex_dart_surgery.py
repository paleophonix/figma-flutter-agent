"""Regex Dart surgery lint gate tests."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LINT = ROOT / "scripts" / "lint_regex_dart_surgery.py"
BASELINE = ROOT / "tests" / "fixtures" / "lint" / "regex_dart_surgery_baseline.txt"


def test_regex_dart_baseline_exists() -> None:
    assert BASELINE.is_file()


def test_regex_dart_gate_passes() -> None:
    result = subprocess.run(
        [sys.executable, str(LINT)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr or result.stdout


def test_regex_dart_collects_known_debt_files() -> None:
    from scripts.lint_regex_dart_surgery import collect_violations

    violations = collect_violations()
    paths = {item.path for item in violations}
    assert "src/figma_flutter_agent/generator/dart/llm_codegen/positioned.py" in paths
    assert "src/figma_flutter_agent/generator/dart/layout_extract.py" in paths
