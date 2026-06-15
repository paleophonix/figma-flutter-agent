"""Mypy strict-island gate for config, errors, and figma packages."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

STRICT_ISLANDS = (
    "src/figma_flutter_agent/config",
    "src/figma_flutter_agent/errors.py",
    "src/figma_flutter_agent/figma",
)


def test_mypy_strict_islands_pass() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "mypy", *STRICT_ISLANDS],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout or result.stderr
