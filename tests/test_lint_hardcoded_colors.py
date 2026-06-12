"""Hardcoded color lint gate tests."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LINT = ROOT / "scripts" / "lint_hardcoded_colors.py"
BASELINE = ROOT / "tests" / "fixtures" / "lint" / "hardcoded_color_baseline.txt"


def test_hardcoded_color_baseline_exists() -> None:
    assert BASELINE.is_file()


def test_hardcoded_color_gate_passes() -> None:
    result = subprocess.run(
        [sys.executable, str(LINT)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr or result.stdout


def test_allowlisted_overlay_requires_comment() -> None:
    from scripts.lint_hardcoded_colors import _line_has_allow_comment

    lines = ['value = "Color(0x1A000000)"  # lint:allow system-overlay']
    assert _line_has_allow_comment(lines, 0)
    assert not _line_has_allow_comment(['value = "Color(0x1A000000)"'], 0)
