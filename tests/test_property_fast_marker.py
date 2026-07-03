"""CI guard: property_fast marker collects tests."""

from __future__ import annotations

import subprocess
import sys


def test_property_fast_marker_collects_tests() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "--collect-only", "-q", "-m", "property_fast"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0
    assert "test session starts" in result.stdout.lower() or "tests collected" in result.stdout.lower()
    assert "no tests collected" not in result.stdout.lower()
